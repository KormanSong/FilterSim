"""필터 프레임워크 핵심 — BaseFilter, ParamSpec, 공통 검증."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from src.signal_context import SignalContext


@dataclass(frozen=True)
class ParamSpec:
    """필터 파라미터 하나의 명세.

    4차의 폼 자동 생성기가 이 명세를 읽어 위젯을 만든다.
    """
    name: str
    label: str
    type: Literal["int", "float", "str"]
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str = ""
    constraint: Literal["odd"] | None = None
    choices: tuple[str, ...] | None = None
    visible_if: str | None = None  # 예: "mode == bandpass"
    decimals: int | None = None
    help_text: str = ""


class BaseFilter(ABC):
    """모든 필터의 부모 클래스.

    새 필터를 만들 때:
      1. 이 클래스를 상속
      2. name, description, params_spec 정의
      3. apply() 구현
      4. filters/__init__.py 레지스트리에 1줄 등록
    """
    name: str = ""
    description: str = ""
    params_spec: tuple[ParamSpec, ...] = ()

    def get_params_spec(self, ctx: SignalContext | None = None) -> tuple[ParamSpec, ...]:
        """ctx 기반으로 동적 bounds를 조정한 ParamSpec을 반환한다.

        기본 구현은 정적 params_spec을 그대로 반환.
        FIR처럼 fs/2 상한이 필요한 필터는 오버라이드.
        """
        return self.params_spec

    def default_params(self, ctx: SignalContext | None = None) -> dict[str, Any]:
        """파라미터 기본값 dict를 반환한다."""
        return {p.name: p.default for p in self.get_params_spec(ctx)}

    def estimated_delay_samples(
        self, ctx: SignalContext, **params: Any
    ) -> float | None:
        """응답 지연의 근사 샘플 수를 반환한다.

        반환값:
          - float: 근사 가능한 고정 지연
          - None: 주파수/입력 의존성이 커서 단일 값으로 표현하기 어려움
        """
        return None

    def validate_params(self, ctx: SignalContext, **params: Any) -> dict[str, Any]:
        """ParamSpec 기반 공통 검증 → 검증 통과된 params dict 반환.

        검증 항목:
          - 알 수 없는 키 → ValueError
          - visible_if False인 파라미터 → 검증 건너뜀, 기본값 채움
          - 누락 파라미터 → 기본값 채움
          - type 변환
          - min/max 범위
          - constraint ("odd")
        실패 시 ValueError.
        """
        specs = {p.name: p for p in self.get_params_spec(ctx)}
        validated: dict[str, Any] = {}

        # 알 수 없는 키 검사
        unknown = set(params.keys()) - set(specs.keys())
        if unknown:
            raise ValueError(
                f"{self.name}: unknown parameter(s): {', '.join(sorted(unknown))}"
            )

        for name, spec in specs.items():
            # visible_if 평가: False이면 기본값으로 채우고 검증 건너뜀
            if spec.visible_if and not _eval_visible_if(spec.visible_if, params, specs):
                validated[name] = spec.default
                continue

            value = params.get(name, spec.default)

            # 타입 변환
            if spec.type == "int":
                value = int(value)
            elif spec.type == "float":
                value = float(value)
            elif spec.type == "str":
                value = str(value)
                if spec.choices and value not in spec.choices:
                    raise ValueError(
                        f"{self.name}: '{name}' must be one of {spec.choices}, got '{value}'"
                    )

            # 범위 검사
            if spec.min is not None and value < spec.min:
                raise ValueError(
                    f"{self.name}: '{name}' = {value} is below minimum {spec.min}"
                )
            if spec.max is not None and value > spec.max:
                raise ValueError(
                    f"{self.name}: '{name}' = {value} is above maximum {spec.max}"
                )

            # 제약 조건
            if spec.constraint == "odd" and isinstance(value, int) and value % 2 == 0:
                raise ValueError(
                    f"{self.name}: '{name}' = {value} must be odd"
                )

            validated[name] = value

        return validated

    @abstractmethod
    def apply(self, data: NDArray[np.float64], ctx: SignalContext, **params: Any) -> NDArray[np.float64]:
        """필터를 적용하고 동일 길이의 배열을 반환한다.

        params는 반드시 validate_params()를 거친 값이어야 한다.
        """
        ...


def _eval_visible_if(expr: str, params: dict[str, Any], specs: dict[str, ParamSpec]) -> bool:
    """visible_if 조건식을 평가한다.

    지원 형식:
      - "name == value"
      - "name != value"
    """
    for op in ("!=", "=="):
        if op in expr:
            lhs, rhs = expr.split(op, 1)
            lhs = lhs.strip()
            rhs = rhs.strip()
            # lhs는 파라미터 이름, rhs는 값
            actual = params.get(lhs, specs[lhs].default if lhs in specs else None)
            actual_str = str(actual)
            if op == "==":
                return actual_str == rhs
            else:
                return actual_str != rhs
    return True  # 파싱 불가 시 보이는 것으로 간주
