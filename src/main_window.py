"""메인 윈도우 — UI 로드, 그래프 관리, 필터 체인 연결, 평가 지표."""

from pathlib import Path

from src.scipy_preload import preload_scipy_dependencies

preload_scipy_dependencies()

import numpy as np
import pyqtgraph as pg
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt
from PySide6.QtGui import QCursor, QAction
from PySide6.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QWidget

from src.csv_loader import load_columns, validate_time_axis
from src.csv_dialog import CSVOpenDialog
from src.signal_context import SignalContext
from src.filter_chain import FilterChain
from src.filters import FILTER_REGISTRY
from src.chain_card import ChainCard
from src.fft_engine import compute_fft
from src.metrics_engine import compute_metrics
from src.resources import resource_path

pg.setConfigOptions(antialias=False)

UI_PATH = resource_path("ui/mainwindow.ui")

# ── 모드별 그래프 설정 ─────────────────────────────────────
# 각 항목: (title, x_label, y_label, log_y)
_PLOT_CONFIGS = {
    "filter": {
        "graphMain": ("Time Domain — Raw (gray) + Filtered (blue)", "Time", "Amplitude", False),
        "graphFFTRaw": ("FFT — Raw (DC removed)", "Frequency (Hz)", "Magnitude (log)", True),
        "graphFFTFiltered": ("FFT — Filtered (DC removed)", "Frequency (Hz)", "Magnitude (log)", True),
    },
    "analysis": {
        "graphMain": ("Time Domain — Raw (gray) + Model (red)", "Time", "Amplitude", False),
        "graphFFTRaw": ("Welch PSD — Residual", "Frequency (Hz)", "PSD (V\u00b2/Hz)", True),
        "graphFFTFiltered": ("", "Frequency (Hz)", "", True),
    },
}


def create_main_window():
    if not UI_PATH.exists():
        raise FileNotFoundError(f"UI file not found: {UI_PATH}")

    loader = QUiLoader()
    ui_file = QFile(str(UI_PATH))
    if not ui_file.open(QFile.ReadOnly):
        raise RuntimeError(f"Cannot open UI file: {UI_PATH}")

    window = loader.load(ui_file)
    ui_file.close()

    if window is None:
        raise RuntimeError(f"Failed to load UI: {loader.errorString()}")

    # 상태 저장용 속성
    window._csv_path = None
    window._time_array = None
    window._data_array = None
    window._signal_ctx = None
    window._filter_chain = FilterChain()
    window._collapsed_states = []
    window._filtered_data = None  # 캐시: metrics 재계산 시 체인 재실행 방지
    window._startup_discard_samples = 0
    window._current_mode = "filter"
    window._duplicate_intervals = 0

    _setup_graphs(window)
    _setup_region(window)
    _init_combos(window)
    _connect_signals(window)
    return window


# ── 초기화 ──────────────────────────────────────────────

def _setup_graphs(window):
    """PyQtGraph 위젯 3개를 .ui의 빈 QWidget 컨테이너에 삽입한다."""
    for obj_name in ("graphMain", "graphFFTRaw", "graphFFTFiltered"):
        container = window.findChild(QWidget, obj_name)
        plot_widget = pg.PlotWidget()
        plot_widget.setAntialiasing(False)
        plot_widget.setBackground("w")
        plot_widget.showGrid(x=True, y=True)
        plot_widget.getPlotItem().setDownsampling(auto=True, mode="peak")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        container.setLayout(layout)
        layout.addWidget(plot_widget)

        setattr(window, f"_plot_{obj_name}", plot_widget)

    # 필터 모드 PlotDataItem — Raw + Filtered 라인 (setData로 갱신)
    main_plot = window._plot_graphMain
    window._line_raw = main_plot.plot(
        pen=pg.mkPen(color=(70, 70, 70), width=2.2), name="Raw"
    )
    window._line_filtered = main_plot.plot(
        pen=pg.mkPen(color=(0, 110, 220), width=2.4), name="Filtered"
    )

    # FFT PlotDataItem
    window._line_fft_raw = window._plot_graphFFTRaw.plot(
        pen=pg.mkPen(color=(70, 70, 70), width=1.5), name="FFT Raw"
    )
    window._line_fft_filtered = window._plot_graphFFTFiltered.plot(
        pen=pg.mkPen(color=(0, 110, 220), width=1.5), name="FFT Filtered"
    )

    for line in (
        window._line_raw,
        window._line_filtered,
        window._line_fft_raw,
        window._line_fft_filtered,
    ):
        line.setClipToView(True)
        line.setDownsampling(auto=True, method="peak")
        line.setSkipFiniteCheck(True)

    # 초기 모드의 제목/축/스케일 적용
    _configure_plots(window, window._current_mode)


def _configure_plots(window, mode: str):
    """모드에 따라 그래프 제목, 축 라벨, 로그 스케일을 일괄 적용한다."""
    config = _PLOT_CONFIGS[mode]
    for obj_name, (title, x_label, y_label, log_y) in config.items():
        plot_widget = getattr(window, f"_plot_{obj_name}")
        plot_widget.setTitle(title)
        plot_widget.setLabel("left", y_label)
        plot_widget.setLabel("bottom", x_label)
        plot_widget.setLogMode(x=False, y=log_y)


def _set_mode(window, mode: str):
    """모드를 전환하고 그래프/UI를 갱신한다.

    현재 filter/analysis 두 모드를 지원한다.
    모드 전환 시 그래프 설정을 변경하고 데이터를 다시 표시한다.
    """
    if window._current_mode == mode:
        return
    window._current_mode = mode
    _configure_plots(window, mode)
    _update_graphs(window)


def _setup_region(window):
    """메인 그래프에 분석 구간 LinearRegionItem을 추가한다.

    초기에는 숨김 상태. 데이터 로드 시 후반 20%에 배치하고 표시.
    """
    region = pg.LinearRegionItem(
        values=(0, 1),
        brush=pg.mkBrush(0, 100, 200, 30),
        pen=pg.mkPen(color=(0, 100, 200, 120), width=1),
        movable=True,
    )
    region.setVisible(False)
    window._plot_graphMain.addItem(region)
    window._analysis_region = region

    # 드래그 완료 시에만 metrics 재계산 (sigRegionChangeFinished)
    region.sigRegionChangeFinished.connect(lambda: _update_metrics(window))


def _init_combos(window):
    """콤보박스 초기값 설정"""
    window.comboFFTWindow.addItems(["None", "Hann", "Hamming", "Blackman"])
    window.comboFilterType.addItems(list(FILTER_REGISTRY.keys()))


def _connect_signals(window):
    """시그널 연결"""
    # 메뉴바: Open CSV (actionOpenCSV는 .ui에서 menubar에 직접 배치)
    action = window.findChild(QAction, "actionOpenCSV")
    if action is not None:
        action.triggered.connect(lambda: _on_open_csv(window))

    window.btnAddFilter.clicked.connect(lambda: _on_add_filter(window))
    window.btnClearChain.clicked.connect(lambda: _on_clear_chain(window))
    window.comboFFTWindow.currentTextChanged.connect(lambda: _update_graphs(window))

    # Metrics 컨트롤
    window.spinHFCutoff.editingFinished.connect(lambda: _update_metrics(window))
    window.checkShowRegion.toggled.connect(
        lambda checked: window._analysis_region.setVisible(
            checked and window._data_array is not None
        )
    )


# ── CSV 흐름 ────────────────────────────────────────────

def _on_open_csv(window):
    """Open CSV → 다이얼로그로 파일 + 열 선택 + 로드."""
    last_path = window._csv_path or ""
    dlg = CSVOpenDialog(window, last_path=last_path)

    if dlg.exec() != CSVOpenDialog.Accepted:
        return  # Cancel → 현재 화면 상태 유지

    path = dlg.selected_path
    time_col = dlg.selected_time_col
    data_col = dlg.selected_data_col

    _load_data(window, path, time_col, data_col)


def _load_data(window, path: str, time_col: str, data_col: str):
    """CSV 로드 → 검증 → 상태 갱신. 실패 시 현재 화면 상태를 유지한다."""
    # busy cursor
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    try:
        time_arr, data_arr, n_total, n_valid = load_columns(path, time_col, data_col)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Failed to load data:\n{e}")
        return
    finally:
        QApplication.restoreOverrideCursor()

    if n_valid < 2:
        QMessageBox.warning(window, "Warning", "Not enough valid data points (need \u2265 2).")
        return

    duplicate_intervals = int(np.sum(np.diff(time_arr) == 0))

    try:
        ctx = validate_time_axis(time_arr, n_total, n_valid)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Time axis validation failed:\n{e}")
        return

    # duplicate timestamp / 불균일 시간축 경고
    if duplicate_intervals > 0 or not ctx.is_uniform:
        details = []
        if duplicate_intervals > 0:
            details.append(
                f"{duplicate_intervals:,} duplicate timestamp interval(s) detected.\n"
                "This can happen with logging artifacts; samples will still be loaded."
            )
        if not ctx.is_uniform:
            details.append("Time axis appears non-uniform.")

        reply = QMessageBox.warning(
            window,
            "Time Axis Warning",
            "\n\n".join(details)
            + f"\n\nEstimated fs = {ctx.fs:.1f} Hz will be used.\n\nContinue anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.No:
            return

    # ── 여기까지 오면 로드 성공 → 상태 갱신 ──

    # 체인 초기화
    window._filter_chain.clear()
    window._collapsed_states.clear()
    window._filtered_data = None
    window._startup_discard_samples = 0
    _rebuild_chain_ui(window)

    # 상태 저장
    window._csv_path = path
    window._time_array = time_arr
    window._data_array = data_arr
    window._signal_ctx = ctx
    window._duplicate_intervals = duplicate_intervals

    # 필터 모드로 복귀 (분석 모드에서 새 파일 로드 시)
    if window._current_mode != "filter":
        window._current_mode = "filter"
        _configure_plots(window, "filter")

    # 분석 구간: 후반 20%
    t_start = time_arr[0]
    t_end = time_arr[-1]
    t_80pct = t_start + (t_end - t_start) * 0.8
    window._analysis_region.setRegion((t_80pct, t_end))
    window._analysis_region.setVisible(window.checkShowRegion.isChecked())

    # HF cutoff 기본값: fs / 20
    default_cutoff = ctx.fs / 20.0
    window.spinHFCutoff.setMaximum(ctx.fs / 2.0)
    window.spinHFCutoff.setValue(default_cutoff)
    window.spinHFCutoff.setEnabled(True)
    window.checkShowRegion.setEnabled(True)

    # 그래프 갱신
    _update_graphs(window)

    # 컨트롤 활성화
    window.comboFilterType.setEnabled(True)
    window.btnAddFilter.setEnabled(True)
    window.btnClearChain.setEnabled(True)
    window.comboFFTWindow.setEnabled(True)

    # Window 타이틀
    window.setWindowTitle(f"MFClab \u2014 {Path(path).name}")

    # 상태 표시
    window.labelStatus.setText(
        f"Total {ctx.n_total:,} / Valid {ctx.n_valid:,} / fs = {ctx.fs:.0f} Hz"
    )


# ── 필터 체인 조작 ──────────────────────────────────────

def _on_add_filter(window):
    """선택된 필터 타입을 체인에 추가"""
    filter_name = window.comboFilterType.currentText()
    filter_cls = FILTER_REGISTRY[filter_name]
    instance = filter_cls()
    defaults = instance.default_params(window._signal_ctx)
    window._filter_chain.add(instance, defaults)
    window._collapsed_states.append(False)
    _rebuild_chain_ui(window)
    _update_graphs(window)


def _on_clear_chain(window):
    """체인 전체 초기화"""
    window._filter_chain.clear()
    window._collapsed_states.clear()
    window._filtered_data = None
    window._startup_discard_samples = 0
    _rebuild_chain_ui(window)
    _update_graphs(window)


def _on_remove_filter(window, chain_index):
    """체인에서 필터 제거"""
    window._filter_chain.remove(chain_index)
    del window._collapsed_states[chain_index]
    _rebuild_chain_ui(window)
    _update_graphs(window)


def _on_toggle_filter(window, chain_index, enabled):
    """필터 활성/비활성 토글"""
    window._filter_chain.set_enabled(chain_index, enabled)
    _update_graphs(window)


def _on_move_filter(window, from_index, to_index):
    """필터 이동"""
    window._filter_chain.move(from_index, to_index)
    states = window._collapsed_states
    states.insert(to_index, states.pop(from_index))
    _rebuild_chain_ui(window)
    _update_graphs(window)


def _on_params_changed(window, chain_index, new_params):
    """필터 파라미터 변경"""
    window._filter_chain.set_params(chain_index, new_params)
    _update_graphs(window)


def _on_collapsed_changed(window, chain_index, collapsed):
    """필터 카드 접힘 상태 변경"""
    window._collapsed_states[chain_index] = collapsed


# ── 그래프 갱신 ─────────────────────────────────────────

def _apply_display_floor(magnitudes):
    """log 스케일 표시용 magnitude floor — 최대값 대비 1e-6 (-120dB) 미만 클램프.

    분석 엔진(compute_fft)은 원본 magnitude를 반환하고,
    이 함수는 그래프 표시 직전에만 적용한다.
    """
    if len(magnitudes) == 0:
        return magnitudes
    mag_max = np.max(magnitudes)
    floor = mag_max * 1e-6
    if floor > 0:
        return np.maximum(magnitudes, floor)
    return magnitudes


def _build_status_text(window) -> str:
    """현재 데이터/필터 상태를 문자열로 구성한다."""
    ctx = window._signal_ctx
    if ctx is None:
        return "No data loaded"

    text = f"Total {ctx.n_total:,} / Valid {ctx.n_valid:,} / fs = {ctx.fs:.0f} Hz"
    duplicate_intervals = getattr(window, "_duplicate_intervals", 0)
    if duplicate_intervals > 0:
        text += f" / Duplicate ts = {duplicate_intervals:,}"

    chain = window._filter_chain
    has_active = any(entry.enabled for entry in chain.entries)
    if not has_active:
        return text

    startup_discard = getattr(window, "_startup_discard_samples", 0)
    if startup_discard > 0:
        warmup_ms = startup_discard * ctx.dt * 1000.0
        text += f" / Warm-up skip = {startup_discard} samples ({warmup_ms:.1f} ms)"

    delay_samples, has_known, has_unknown = chain.estimate_delay_samples(ctx)
    if has_known:
        delay_ms = delay_samples * ctx.dt * 1000.0
        text += f" / Delay ~ {delay_ms:.1f} ms"
        if has_unknown:
            text += " +"
    elif has_unknown:
        text += " / Delay: varies"

    return text


def _update_graphs(window):
    """현재 모드에 따라 적절한 그래프 갱신 함수를 호출한다."""
    if window._current_mode == "filter":
        _update_filter_mode(window)
    else:
        _update_analysis_mode(window)


def _update_filter_mode(window):
    """필터 모드: Raw + Filtered + FFT Raw + FFT Filtered를 갱신한다."""
    time_arr = window._time_array
    data_arr = window._data_array
    ctx = window._signal_ctx

    if time_arr is None or data_arr is None:
        return

    window_name = window.comboFFTWindow.currentText()
    filtered_data = None
    filter_error = False

    # ── 1) Time domain: Raw ──
    window._line_raw.setData(time_arr, data_arr)

    # ── 2) Time domain: Filtered ──
    chain = window._filter_chain
    has_active = any(e.enabled for e in chain.entries)

    if len(chain) == 0 or not has_active:
        window._line_filtered.setData([], [])
        window._filtered_data = None
        window._startup_discard_samples = 0
    else:
        try:
            filtered_data = chain.execute(data_arr, ctx)
            startup_discard = chain.estimate_startup_discard_samples(
                ctx, len(filtered_data)
            )
            window._startup_discard_samples = startup_discard

            if startup_discard >= len(filtered_data):
                window._line_filtered.setData([], [])
            else:
                window._line_filtered.setData(
                    time_arr[startup_discard:], filtered_data[startup_discard:]
                )
            window._filtered_data = filtered_data  # 캐시
        except (ValueError, Exception) as e:
            window._line_filtered.setData([], [])
            window._filtered_data = None
            window._startup_discard_samples = 0
            window.labelStatus.setText(f"Filter error: {e}")
            filter_error = True

    # ── 3) FFT: Raw (항상 갱신) ──
    raw_fft_input = data_arr
    if filtered_data is not None and not filter_error:
        raw_fft_input = data_arr[window._startup_discard_samples:]

    freqs_raw, mags_raw = compute_fft(raw_fft_input, ctx.fs, window_name)
    window._line_fft_raw.setData(freqs_raw, _apply_display_floor(mags_raw))

    # ── 4) FFT: Filtered (활성 필터 있고 에러 없을 때만) ──
    if filtered_data is not None and not filter_error:
        fft_input = filtered_data[window._startup_discard_samples:]
        freqs_f, mags_f = compute_fft(fft_input, ctx.fs, window_name)
        window._line_fft_filtered.setData(freqs_f, _apply_display_floor(mags_f))
    else:
        window._line_fft_filtered.setData([], [])

    # ── 상태 표시 (에러 없는 경우만 갱신) ──
    if not filter_error:
        window.labelStatus.setText(_build_status_text(window))

    # ── Metrics 갱신 ──
    _update_metrics(window)


def _update_analysis_mode(window):
    """분석 모드 그래프 갱신. (9-2 이후에서 구현 예정)

    현재는 필터 모드 라인을 클리어하고 상태 메시지만 표시한다.
    """
    window._line_raw.setData([], [])
    window._line_filtered.setData([], [])
    window._line_fft_raw.setData([], [])
    window._line_fft_filtered.setData([], [])

    if window._data_array is not None:
        window.labelStatus.setText("Analysis mode \u2014 not yet implemented")


def _update_metrics(window):
    """평가 지표를 (재)계산하여 UI에 표시한다.

    _update_filter_mode()의 마지막에 호출되거나,
    spinHFCutoff / LinearRegionItem 변경 시 단독 호출된다.
    체인 재실행 없이 캐시된 _filtered_data를 사용한다.
    """
    data_arr = window._data_array
    filtered = window._filtered_data
    ctx = window._signal_ctx
    time_arr = window._time_array
    startup_discard = getattr(window, "_startup_discard_samples", 0)

    # 데이터 또는 필터 결과 없으면 초기화
    if data_arr is None or filtered is None or ctx is None or time_arr is None:
        window.labelSettledStd.setText("\u2014")
        window.labelHFRMS.setText("\u2014")
        return

    if startup_discard >= len(filtered):
        window.labelSettledStd.setText("\u2014")
        window.labelHFRMS.setText("\u2014")
        return

    effective_time = time_arr[startup_discard:]
    effective_raw = data_arr[startup_discard:]
    effective_filtered = filtered[startup_discard:]

    # 분석 구간 → 인덱스 변환
    t_min, t_max = window._analysis_region.getRegion()
    start_idx = int(np.searchsorted(effective_time, t_min, side="left"))
    end_idx = int(np.searchsorted(effective_time, t_max, side="right"))

    if end_idx - start_idx < 2:
        window.labelSettledStd.setText("\u2014")
        window.labelHFRMS.setText("\u2014")
        return

    cutoff_hz = window.spinHFCutoff.value()

    result = compute_metrics(
        effective_raw, effective_filtered, ctx.fs, cutoff_hz, start_idx, end_idx
    )

    # Settled std 표시
    if result.raw_settled_std > 0:
        reduction = (1.0 - result.filt_settled_std / result.raw_settled_std) * 100.0
        window.labelSettledStd.setText(
            f"{result.raw_settled_std:.2f} \u2192 {result.filt_settled_std:.2f} "
            f"({reduction:+.0f}%)"
        )
    else:
        window.labelSettledStd.setText(
            f"{result.raw_settled_std:.2f} \u2192 {result.filt_settled_std:.2f}"
        )

    # HF RMS 표시
    if result.raw_hf_rms > 0:
        hf_reduction = (1.0 - result.filt_hf_rms / result.raw_hf_rms) * 100.0
        window.labelHFRMS.setText(
            f"{result.raw_hf_rms:.2f} \u2192 {result.filt_hf_rms:.2f} "
            f"({hf_reduction:+.0f}%)"
        )
    else:
        window.labelHFRMS.setText(
            f"{result.raw_hf_rms:.2f} \u2192 {result.filt_hf_rms:.2f}"
        )


# ── 체인 UI 재구성 ──────────────────────────────────────

def _rebuild_chain_ui(window):
    """filterChainVLayout 내 카드를 전부 재생성한다."""
    layout = window.filterChainVLayout

    # 기존 위젯 전부 제거
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

    chain = window._filter_chain
    entries = chain.entries
    n = len(entries)

    collapsed_states = window._collapsed_states
    for i, entry in enumerate(entries):
        card = ChainCard(
            chain_index=i,
            filter_instance=entry.filter_instance,
            params=entry.params,
            enabled=entry.enabled,
            ctx=window._signal_ctx,
            is_first=(i == 0),
            is_last=(i == n - 1),
            collapsed=collapsed_states[i] if i < len(collapsed_states) else False,
        )
        card.remove_requested.connect(
            lambda idx, _w=window: _on_remove_filter(_w, idx)
        )
        card.toggle_requested.connect(
            lambda idx, en, _w=window: _on_toggle_filter(_w, idx, en)
        )
        card.move_requested.connect(
            lambda fr, to, _w=window: _on_move_filter(_w, fr, to)
        )
        card.params_changed.connect(
            lambda idx, p, _w=window: _on_params_changed(_w, idx, p)
        )
        card.collapsed_changed.connect(
            lambda idx, c, _w=window: _on_collapsed_changed(_w, idx, c)
        )
        layout.addWidget(card)

    # 하단 스페이서 — 카드가 위로 정렬되도록
    layout.addStretch()
