"""필터 체인 카드 UI — 체인 내 각 필터 하나를 나타내는 위젯."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.filters.base import BaseFilter, ParamSpec
from src.param_form import ParamForm
from src.signal_context import SignalContext


class ChainCard(QGroupBox):
    """체인 내 필터 하나를 나타내는 카드 위젯.

    시그널:
        remove_requested(int): 이 카드의 chain_index 제거 요청
        move_requested(int, int): from_index, to_index 이동 요청
        toggle_requested(int, bool): chain_index, enabled 토글 요청
        params_changed(int, dict): chain_index, new_params 변경 알림
        collapsed_changed(int, bool): chain_index, collapsed 접힘 상태 변경
    """

    remove_requested = Signal(int)
    move_requested = Signal(int, int)
    toggle_requested = Signal(int, bool)
    params_changed = Signal(int, dict)
    collapsed_changed = Signal(int, bool)

    def __init__(
        self,
        chain_index: int,
        filter_instance: BaseFilter,
        params: dict[str, Any],
        enabled: bool,
        ctx: SignalContext,
        is_first: bool = False,
        is_last: bool = False,
        collapsed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chain_index = chain_index

        self.setTitle(f"#{chain_index + 1} {filter_instance.name}")

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        self.setLayout(main_layout)

        # ── 상단 바: 접기 토글 + 활성 체크 + 이동 + 삭제 ──
        bar = QHBoxLayout()

        self._btn_collapse = QToolButton()
        self._btn_collapse.setFixedWidth(24)
        self._btn_collapse.clicked.connect(self._on_collapse_toggle)
        bar.addWidget(self._btn_collapse)

        self._chk_enabled = QCheckBox("Enabled")
        self._chk_enabled.setChecked(enabled)
        self._chk_enabled.toggled.connect(self._on_toggle)
        bar.addWidget(self._chk_enabled)

        bar.addStretch()

        self._btn_up = QPushButton("\u25b2")
        self._btn_up.setFixedWidth(28)
        self._btn_up.setEnabled(not is_first)
        self._btn_up.clicked.connect(self._on_move_up)
        bar.addWidget(self._btn_up)

        self._btn_down = QPushButton("\u25bc")
        self._btn_down.setFixedWidth(28)
        self._btn_down.setEnabled(not is_last)
        self._btn_down.clicked.connect(self._on_move_down)
        bar.addWidget(self._btn_down)

        self._btn_remove = QPushButton("\u2715")
        self._btn_remove.setFixedWidth(28)
        self._btn_remove.clicked.connect(self._on_remove)
        bar.addWidget(self._btn_remove)

        main_layout.addLayout(bar)

        # ── 파라미터 폼 ──
        specs = filter_instance.get_params_spec(ctx)
        self._param_form = ParamForm(specs, params, self)
        self._param_form.params_changed.connect(self._on_params_changed)
        main_layout.addWidget(self._param_form)

        # 접힘 상태 초기 적용
        self._collapsed = collapsed
        self._param_form.setVisible(not collapsed)
        self._btn_collapse.setText("\u25b6" if collapsed else "\u25bc")

    def _on_collapse_toggle(self) -> None:
        """파라미터 폼 접기/펼치기 토글."""
        self._collapsed = not self._collapsed
        self._param_form.setVisible(not self._collapsed)
        self._btn_collapse.setText("\u25b6" if self._collapsed else "\u25bc")
        self.collapsed_changed.emit(self._chain_index, self._collapsed)

    def _on_toggle(self, checked: bool) -> None:
        self.toggle_requested.emit(self._chain_index, checked)

    def _on_move_up(self) -> None:
        self.move_requested.emit(self._chain_index, self._chain_index - 1)

    def _on_move_down(self) -> None:
        self.move_requested.emit(self._chain_index, self._chain_index + 1)

    def _on_remove(self) -> None:
        self.remove_requested.emit(self._chain_index)

    def _on_params_changed(self, new_params: dict) -> None:
        self.params_changed.emit(self._chain_index, new_params)
