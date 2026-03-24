"""Second-order low-pass filters implemented as MCU-friendly biquads."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.filters.base import BaseFilter, ParamSpec
from src.signal_context import SignalContext

_EPSILON = 1e-12
_C_FRIENDLY_MAX_CUTOFF_RATIO = 0.45
_BESSEL_PRACTICAL_Q = 0.57735026919


def _apply_biquad(
    data: NDArray[np.float64],
    b: NDArray[np.float64],
    a: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Apply a single biquad using a direct-form difference equation.

    y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
    """
    result = data.astype(np.float64, copy=True)
    if result.size == 0:
        return result

    a0 = float(a[0])
    if abs(a0) < _EPSILON:
        raise ValueError("Biquad denominator a0 must be non-zero")

    b0 = float(b[0] / a0)
    b1 = float(b[1] / a0)
    b2 = float(b[2] / a0)
    a1 = float(a[1] / a0)
    a2 = float(a[2] / a0)

    x1 = x2 = float(result[0])
    y1 = y2 = float(result[0])
    result[0] = y1

    for i in range(1, result.size):
        x0 = float(result[i])
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        result[i] = y0
        x2, x1 = x1, x0
        y2, y1 = y1, y0

    return result


class _BaseSecondOrderLowpassFilter(BaseFilter):
    cutoff_help_text = (
        "Second-order post-lead low-pass cutoff. Useful for suppressing overshoot/"
        "undershoot and high-frequency noise after compensation, but cannot undo "
        "aliasing already folded into the 1 kHz data."
    )
    params_spec = (
        ParamSpec(
            name="cutoff_hz",
            label="Cutoff",
            type="float",
            default=7.0,
            min=0.001,
            max=None,
            step=0.05,
            decimals=3,
            unit="Hz",
            help_text=cutoff_help_text,
        ),
    )

    def get_params_spec(self, ctx: SignalContext | None = None) -> tuple[ParamSpec, ...]:
        if ctx is None:
            return self.params_spec

        nyquist = ctx.fs / 2.0
        c_friendly_limit = ctx.fs * _C_FRIENDLY_MAX_CUTOFF_RATIO
        max_cutoff = min(nyquist - 0.1, c_friendly_limit)
        return tuple(
            replace(spec, max=max_cutoff) if spec.name == "cutoff_hz" else spec
            for spec in self.params_spec
        )

    def _design_biquad(self, cutoff_hz: float, fs: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        raise NotImplementedError

    def apply(
        self, data: NDArray[np.float64], ctx: SignalContext, **params: Any
    ) -> NDArray[np.float64]:
        p = self.validate_params(ctx, **params)
        cutoff_hz: float = p["cutoff_hz"]

        if ctx.dt <= 0:
            raise ValueError(f"{self.name}: ctx.dt must be positive, got {ctx.dt}")

        b, a = self._design_biquad(cutoff_hz, ctx.fs)
        return _apply_biquad(data, b, a)


class BesselLowpassFilter(_BaseSecondOrderLowpassFilter):
    name = "Bessel LPF (2nd)"
    description = (
        "Second-order low-pass biquad using a C-friendly fixed-Q Bessel-like formulation"
    )

    def _design_biquad(
        self, cutoff_hz: float, fs: float
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        fc = _clamp_cutoff_hz(fs, cutoff_hz)
        k = float(np.tan(np.pi * fc / fs))
        q = _BESSEL_PRACTICAL_Q
        norm = 1.0 / (1.0 + (k / q) + (k * k))

        b = np.asarray(
            [
                (k * k) * norm,
                2.0 * (k * k) * norm,
                (k * k) * norm,
            ],
            dtype=np.float64,
        )
        a = np.asarray(
            [
                1.0,
                2.0 * ((k * k) - 1.0) * norm,
                (1.0 - (k / q) + (k * k)) * norm,
            ],
            dtype=np.float64,
        )
        return b, a


def _clamp_cutoff_hz(fs: float, cutoff_hz: float) -> float:
    """Clamp cutoff to the MCU-friendly operating range."""
    if fs <= 0.0:
        return 0.001

    clamped = max(0.001, float(cutoff_hz))
    return min(clamped, fs * _C_FRIENDLY_MAX_CUTOFF_RATIO)
