"""Second-order low-pass filters implemented as MCU-friendly biquads."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.filters.base import BaseFilter, ParamSpec
from src.signal_context import SignalContext

_EPSILON = 1e-12


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
        return tuple(
            replace(spec, max=nyquist - 0.1) if spec.name == "cutoff_hz" else spec
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
        "Second-order Bessel low-pass biquad for post-lead smoothing with minimal step overshoot"
    )

    def _design_biquad(
        self, cutoff_hz: float, fs: float
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        from scipy.signal import bessel

        b, a = bessel(
            2,
            cutoff_hz,
            btype="lowpass",
            analog=False,
            output="ba",
            fs=fs,
            norm="mag",
        )
        return np.asarray(b, dtype=np.float64), np.asarray(a, dtype=np.float64)
