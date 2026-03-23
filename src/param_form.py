"""ParamSpec 기반 자동 폼 생성기.

ParamSpec 목록을 받아 QWidget 폼을 생성하고,
파라미터 값이 변경되면 시그널을 발생시킨다.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from src.filters.base import ParamSpec
from src.signal_context import SignalContext


class ParamForm(QWidget):
    """ParamSpec 목록에서 자동 생성되는 파라미터 편집 폼.

    params_changed 시그널로 변경된 전체 파라미터 dict를 내보낸다.
    """

    params_changed = Signal(dict)

    def __init__(
        self,
        specs: tuple[ParamSpec, ...],
        initial_params: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._specs = specs
        self._widgets: dict[str, QWidget] = {}
        self._visibility_rules: list[tuple[str, str]] = []  # (param_name, visible_if)

        layout = QFormLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(layout)

        for spec in specs:
            widget = self._create_widget(spec, initial_params.get(spec.name, spec.default))
            self._widgets[spec.name] = widget

            label = QLabel(spec.label)
            if spec.unit:
                label.setText(f"{spec.label} ({spec.unit})")
            if spec.help_text:
                label.setToolTip(spec.help_text)
                widget.setToolTip(spec.help_text)

            layout.addRow(label, widget)

            if spec.visible_if:
                self._visibility_rules.append((spec.name, spec.visible_if))

        # 초기 가시성 업데이트
        self._update_visibility()

    def _create_widget(self, spec: ParamSpec, value: Any) -> QWidget:
        """ParamSpec 타입에 맞는 위젯을 생성한다."""
        if spec.choices:
            combo = QComboBox()
            combo.addItems(list(spec.choices))
            combo.setCurrentText(str(value))
            combo.currentTextChanged.connect(self._on_value_changed)
            return combo

        if spec.type == "int":
            spin = QSpinBox()
            min_val = int(spec.min) if spec.min is not None else 0
            spin.setMinimum(min_val)
            spin.setMaximum(int(spec.max) if spec.max is not None else 999999)
            # odd 제약: step=2, 최소값을 홀수로 보정
            if spec.constraint == "odd":
                spin.setSingleStep(2)
                if min_val % 2 == 0:
                    spin.setMinimum(min_val + 1)
            else:
                spin.setSingleStep(int(spec.step) if spec.step is not None else 1)
            spin.setValue(int(value))
            spin.editingFinished.connect(self._on_value_changed)
            return spin

        if spec.type == "float":
            spin = QDoubleSpinBox()
            spin.setDecimals(_resolve_float_decimals(spec))
            spin.setMinimum(spec.min if spec.min is not None else 0.0)
            spin.setMaximum(spec.max if spec.max is not None else 999999.0)
            spin.setSingleStep(spec.step if spec.step is not None else 1.0)
            spin.setValue(float(value))
            spin.editingFinished.connect(self._on_value_changed)
            return spin

        # fallback: str 타입
        combo = QComboBox()
        combo.addItems([str(value)])
        combo.setCurrentText(str(value))
        return combo

    def _on_value_changed(self) -> None:
        """위젯 값 변경 → 가시성 업데이트 → params_changed 시그널 발생."""
        self._update_visibility()
        self.params_changed.emit(self.get_params())

    def _update_visibility(self) -> None:
        """visible_if 조건에 따라 위젯 행의 가시성을 업데이트한다."""
        current = self.get_params()
        layout: QFormLayout = self.layout()

        for param_name, expr in self._visibility_rules:
            widget = self._widgets[param_name]
            visible = _eval_visible_if_simple(expr, current)

            # 위젯과 레이블 모두 숨기기/보이기
            row_index = -1
            for i in range(layout.rowCount()):
                field_item = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                if field_item and field_item.widget() is widget:
                    row_index = i
                    break

            if row_index >= 0:
                widget.setVisible(visible)
                label_item = layout.itemAt(row_index, QFormLayout.ItemRole.LabelRole)
                if label_item and label_item.widget():
                    label_item.widget().setVisible(visible)

    def get_params(self) -> dict[str, Any]:
        """현재 폼의 모든 파라미터 값을 dict로 반환한다."""
        result: dict[str, Any] = {}
        for spec in self._specs:
            widget = self._widgets[spec.name]
            if isinstance(widget, QComboBox):
                result[spec.name] = widget.currentText()
            elif isinstance(widget, QSpinBox):
                result[spec.name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                result[spec.name] = widget.value()
            else:
                result[spec.name] = spec.default
        return result


def _eval_visible_if_simple(expr: str, params: dict[str, Any]) -> bool:
    """visible_if 조건식 평가 (== / != 지원)."""
    for op in ("!=", "=="):
        if op in expr:
            lhs, rhs = expr.split(op, 1)
            lhs = lhs.strip()
            rhs = rhs.strip()
            actual = str(params.get(lhs, ""))
            if op == "==":
                return actual == rhs
            else:
                return actual != rhs
    return True


def _resolve_float_decimals(spec: ParamSpec) -> int:
    """float 파라미터 표시 소수점 자릿수를 결정한다."""
    if spec.decimals is not None:
        return spec.decimals

    candidates = [spec.default, spec.min, spec.step]
    decimals = max((_count_decimals(v) for v in candidates if isinstance(v, (int, float))), default=2)
    return max(2, min(decimals, 6))


def _count_decimals(value: float) -> int:
    """값을 무리 없이 입력할 수 있는 소수점 자릿수를 계산한다."""
    text = f"{float(value):.12f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])
