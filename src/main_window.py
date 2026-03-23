"""메인 윈도우 — UI 로드, 그래프 관리, 필터 체인 연결."""

from pathlib import Path

from src.scipy_preload import preload_scipy_dependencies

preload_scipy_dependencies()

import numpy as np
import pyqtgraph as pg
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QVBoxLayout, QWidget

from src.csv_loader import read_headers, load_columns, validate_time_axis
from src.signal_context import SignalContext
from src.filter_chain import FilterChain
from src.filters import FILTER_REGISTRY
from src.chain_card import ChainCard
from src.fft_engine import compute_fft
from src.resources import resource_path

pg.setConfigOptions(antialias=False)

UI_PATH = resource_path("ui/mainwindow.ui")


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

    _setup_graphs(window)
    _init_combos(window)
    _connect_signals(window)
    return window


# ── 초기화 ──────────────────────────────────────────────

def _setup_graphs(window):
    """PyQtGraph 위젯 3개를 .ui의 빈 QWidget 컨테이너에 삽입"""
    graph_configs = [
        ("graphMain", "Time Domain — Raw (gray) + Filtered (blue)", "Time", "Amplitude"),
        ("graphFFTRaw", "FFT — Raw (DC removed)", "Frequency (Hz)", "Magnitude (log)"),
        ("graphFFTFiltered", "FFT — Filtered (DC removed)", "Frequency (Hz)", "Magnitude (log)"),
    ]

    for obj_name, title, x_label, y_label in graph_configs:
        container = window.findChild(QWidget, obj_name)
        plot_widget = pg.PlotWidget()
        plot_widget.setAntialiasing(False)
        plot_widget.setBackground("w")
        plot_widget.setTitle(title)
        plot_widget.setLabel("left", y_label)
        plot_widget.setLabel("bottom", x_label)
        plot_widget.showGrid(x=True, y=True)
        plot_widget.getPlotItem().setDownsampling(auto=True, mode="peak")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        container.setLayout(layout)
        layout.addWidget(plot_widget)

        setattr(window, f"_plot_{obj_name}", plot_widget)

    # PlotDataItem — Raw + Filtered 라인 (setData로 갱신)
    main_plot = window._plot_graphMain
    window._line_raw = main_plot.plot(
        pen=pg.mkPen(color=(70, 70, 70), width=2.2), name="Raw"
    )
    window._line_filtered = main_plot.plot(
        pen=pg.mkPen(color=(0, 110, 220), width=2.4), name="Filtered"
    )

    # FFT 그래프 log-y 스케일
    window._plot_graphFFTRaw.setLogMode(x=False, y=True)
    window._plot_graphFFTFiltered.setLogMode(x=False, y=True)

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
        # 성능 우선: 직선 세그먼트만 그리고, 뷰 범위 밖 포인트와 finite 검사를 줄인다.
        line.setClipToView(True)
        line.setDownsampling(auto=True, method="peak")
        line.setSkipFiniteCheck(True)


def _init_combos(window):
    """콤보박스 초기값 설정"""
    # FFT Window
    window.comboFFTWindow.addItems(["None", "Hann", "Hamming", "Blackman"])

    # Filter Type — 레지스트리에서 이름 채우기
    window.comboFilterType.addItems(list(FILTER_REGISTRY.keys()))


def _connect_signals(window):
    """버튼 시그널 연결"""
    window.btnOpenCSV.clicked.connect(lambda: _on_open_csv(window))
    window.btnLoadData.clicked.connect(lambda: _on_load_data(window))
    window.btnAddFilter.clicked.connect(lambda: _on_add_filter(window))
    window.btnClearChain.clicked.connect(lambda: _on_clear_chain(window))
    window.comboFFTWindow.currentTextChanged.connect(lambda: _update_graphs(window))


# ── CSV 흐름 ────────────────────────────────────────────

def _on_open_csv(window):
    """CSV 파일 선택 → 헤더 읽기 → 콤보박스 채우기"""
    path, _ = QFileDialog.getOpenFileName(
        window, "Open CSV File", "", "CSV Files (*.csv);;All Files (*)"
    )
    if not path:
        return

    try:
        headers = read_headers(path)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Failed to read CSV headers:\n{e}")
        return

    if len(headers) < 2:
        QMessageBox.warning(window, "Warning", "CSV must have at least 2 columns.")
        return

    window._csv_path = path

    window.comboTimeCol.clear()
    window.comboDataCol.clear()
    window.comboTimeCol.addItems(headers)
    window.comboDataCol.addItems(headers)

    # Data 열은 두 번째 컬럼을 기본 선택
    if len(headers) >= 2:
        window.comboDataCol.setCurrentIndex(1)

    window.btnLoadData.setEnabled(True)
    window.labelStatus.setText(f"File: {Path(path).name} — Select columns and load")


def _on_load_data(window):
    """선택 열 로드 → 시간축 검증 → 그래프 표시"""
    path = window._csv_path
    time_col = window.comboTimeCol.currentText()
    data_col = window.comboDataCol.currentText()

    if time_col == data_col:
        QMessageBox.warning(window, "Warning", "Time and Data columns must be different.")
        return

    # busy cursor — 대용량 CSV 로드 중 시각적 피드백
    QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
    try:
        time_arr, data_arr, n_total, n_valid = load_columns(path, time_col, data_col)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Failed to load data:\n{e}")
        return
    finally:
        QApplication.restoreOverrideCursor()

    if n_valid < 2:
        QMessageBox.warning(window, "Warning", "Not enough valid data points (need ≥ 2).")
        return

    try:
        ctx = validate_time_axis(time_arr, n_total, n_valid)
    except Exception as e:
        QMessageBox.critical(window, "Error", f"Time axis validation failed:\n{e}")
        return

    # 불균일 경고
    if not ctx.is_uniform:
        reply = QMessageBox.warning(
            window,
            "Non-uniform Time Axis",
            f"Time axis appears non-uniform.\n"
            f"Estimated fs = {ctx.fs:.1f} Hz will be used.\n\n"
            f"Continue anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.No:
            return

    # 새 데이터 로드 → 전체 상태 초기화 (재로드 시 이전 에러 상태 해제)
    window._filter_chain.clear()
    window._collapsed_states.clear()
    _rebuild_chain_ui(window)

    # 상태 저장
    window._time_array = time_arr
    window._data_array = data_arr
    window._signal_ctx = ctx

    # 그래프 갱신
    _update_graphs(window)

    # 필터/FFT 컨트롤 활성화
    window.comboFilterType.setEnabled(True)
    window.btnAddFilter.setEnabled(True)
    window.btnClearChain.setEnabled(True)
    window.comboFFTWindow.setEnabled(True)

    # Window 타이틀 갱신
    filename = Path(path).name
    window.setWindowTitle(f"MFClab — {filename}")

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

    chain = window._filter_chain
    has_active = any(entry.enabled for entry in chain.entries)
    if not has_active:
        return text

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
    """Raw + Filtered + FFT Raw + FFT Filtered를 단일 사이클로 갱신한다."""
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
    else:
        try:
            filtered_data = chain.execute(data_arr, ctx)
            window._line_filtered.setData(time_arr, filtered_data)
        except (ValueError, Exception) as e:
            window._line_filtered.setData([], [])
            window.labelStatus.setText(f"Filter error: {e}")
            filter_error = True

    # ── 3) FFT: Raw (항상 갱신) ──
    freqs_raw, mags_raw = compute_fft(data_arr, ctx.fs, window_name)
    window._line_fft_raw.setData(freqs_raw, _apply_display_floor(mags_raw))

    # ── 4) FFT: Filtered (활성 필터 있고 에러 없을 때만) ──
    if filtered_data is not None and not filter_error:
        freqs_f, mags_f = compute_fft(filtered_data, ctx.fs, window_name)
        window._line_fft_filtered.setData(freqs_f, _apply_display_floor(mags_f))
    else:
        window._line_fft_filtered.setData([], [])

    # ── 상태 표시 (에러 없는 경우만 갱신) ──
    if not filter_error:
        window.labelStatus.setText(_build_status_text(window))


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
