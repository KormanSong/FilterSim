"""FIR 필터 — firwin + causal single-pass filtering, 동적 bounds."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.signal_context import SignalContext
from src.filters.base import BaseFilter, ParamSpec

_MIN_SAMPLES_FOR_FIR = 10


class FIRFilter(BaseFilter):
    name = "FIR"
    description = "Causal FIR filter (Low/High/Band Pass) with firwin + single-pass apply"
    params_spec = (
        ParamSpec(
            name="mode",
            label="Mode",
            type="str",
            default="lowpass",
            choices=("lowpass", "highpass", "bandpass"),
        ),
        ParamSpec(
            name="cutoff_low",
            label="Cutoff Low",
            type="float",
            default=100.0,
            min=0.1,
            max=None,  # 동적: fs/2 - 런타임에 결정
            step=1.0,
            unit="Hz",
            visible_if="mode != highpass",
        ),
        ParamSpec(
            name="cutoff_high",
            label="Cutoff High",
            type="float",
            default=200.0,
            min=0.1,
            max=None,  # 동적: fs/2
            step=1.0,
            unit="Hz",
            visible_if="mode != lowpass",
        ),
        ParamSpec(
            name="numtaps",
            label="Num Taps",
            type="int",
            default=9,
            min=5,
            max=1001,
            step=2,
            unit="taps",
            constraint="odd",
        ),
    )

    def default_params(self, ctx: SignalContext | None = None) -> dict[str, Any]:
        """cutoff 기본값이 nyquist를 초과하면 clamp."""
        defaults = super().default_params(ctx)
        if ctx is not None:
            nyquist_limit = ctx.fs / 2.0 - 0.1
            for key in ("cutoff_low", "cutoff_high"):
                if defaults[key] > nyquist_limit:
                    defaults[key] = round(nyquist_limit, 1)
        return defaults

    def estimated_delay_samples(
        self, ctx: SignalContext, **params: Any
    ) -> float | None:
        p = self.validate_params(ctx, **params)
        numtaps: int = p["numtaps"]
        return (numtaps - 1) / 2.0

    def get_params_spec(self, ctx: SignalContext | None = None) -> tuple[ParamSpec, ...]:
        """cutoff의 max를 ctx.fs / 2로 동적 조정."""
        if ctx is None:
            return self.params_spec

        nyquist = ctx.fs / 2.0
        adjusted = []
        for spec in self.params_spec:
            if spec.name in ("cutoff_low", "cutoff_high"):
                spec = replace(spec, max=nyquist - 0.1)
            adjusted.append(spec)
        return tuple(adjusted)

    def apply(
        self, data: NDArray[np.float64], ctx: SignalContext, **params: Any
    ) -> NDArray[np.float64]:
        from scipy.signal import firwin, lfilter

        p = self.validate_params(ctx, **params)
        mode: str = p["mode"]
        cutoff_low: float = p["cutoff_low"]
        cutoff_high: float = p["cutoff_high"]
        numtaps: int = p["numtaps"]
        nyquist = ctx.fs / 2.0

        # 짧은 데이터 대응: numtaps 축소
        if len(data) < _MIN_SAMPLES_FOR_FIR:
            return data.copy()

        max_taps = len(data) // 3
        if max_taps < 5:
            return data.copy()
        if numtaps > max_taps:
            numtaps = max_taps | 1  # 홀수 보장

        # firwin 파라미터 구성
        if mode == "lowpass":
            if cutoff_low >= nyquist:
                raise ValueError(f"FIR: cutoff_low ({cutoff_low}) must be < Nyquist ({nyquist})")
            coeffs = firwin(numtaps, cutoff_low, fs=ctx.fs, pass_zero="lowpass")
        elif mode == "highpass":
            if cutoff_high >= nyquist:
                raise ValueError(f"FIR: cutoff_high ({cutoff_high}) must be < Nyquist ({nyquist})")
            coeffs = firwin(numtaps, cutoff_high, fs=ctx.fs, pass_zero="highpass")
        elif mode == "bandpass":
            if cutoff_low >= cutoff_high:
                raise ValueError(
                    f"FIR: cutoff_low ({cutoff_low}) must be < cutoff_high ({cutoff_high})"
                )
            if cutoff_high >= nyquist:
                raise ValueError(f"FIR: cutoff_high ({cutoff_high}) must be < Nyquist ({nyquist})")
            coeffs = firwin(numtaps, [cutoff_low, cutoff_high], fs=ctx.fs, pass_zero="bandpass")
        else:
            raise ValueError(f"FIR: unknown mode '{mode}'")

        # single-pass causal FIR — 실제 펌웨어와 같은 방향으로만 누적한다.
        result = lfilter(coeffs, 1.0, data)
        return np.asarray(result, dtype=np.float64)
