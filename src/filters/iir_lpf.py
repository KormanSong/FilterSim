"""First-order RC IIR low-pass filter used widely in embedded codebases."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.filters.base import BaseFilter, ParamSpec
from src.signal_context import SignalContext

_MICRO_TO_BASE = 1e-6


class IIRLowpassFilter(BaseFilter):
    name = "IIR LPF"
    description = "First-order RC low-pass (y[n] = y[n-1] + alpha * (x[n] - y[n-1]))"
    params_spec = (
        ParamSpec(
            name="resistor_ohms",
            label="Resistor",
            type="float",
            default=1000.0,
            min=0.1,
            max=1_000_000.0,
            step=10.0,
            unit="ohm",
        ),
        ParamSpec(
            name="capacitor_uf",
            label="Capacitor",
            type="float",
            default=10.0,
            min=0.001,
            max=1_000_000.0,
            step=1.0,
            unit="uF",
        ),
    )

    def apply(
        self, data: NDArray[np.float64], ctx: SignalContext, **params: Any
    ) -> NDArray[np.float64]:
        p = self.validate_params(ctx, **params)
        resistor_ohms: float = p["resistor_ohms"]
        capacitor_uf: float = p["capacitor_uf"]

        if ctx.dt <= 0:
            raise ValueError(f"{self.name}: ctx.dt must be positive, got {ctx.dt}")

        result = data.astype(np.float64, copy=True)
        if result.size == 0:
            return result

        rc_seconds = resistor_ohms * capacitor_uf * _MICRO_TO_BASE
        alpha = ctx.dt / (rc_seconds + ctx.dt)

        previous = float(result[0])
        result[0] = previous

        for i in range(1, result.size):
            previous = previous + alpha * (float(result[i]) - previous)
            result[i] = previous

        return result
