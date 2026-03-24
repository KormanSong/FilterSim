"""Second-order critically damped low-pass filter implemented as cascaded EMA."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.filters.base import BaseFilter, ParamSpec
from src.signal_context import SignalContext

_MICRO_TO_BASE = 1e-6


class CriticalDampedLowpassFilter(BaseFilter):
    name = "IIR LPF (2차)"
    description = (
        "Second-order critically damped low-pass using two cascaded EMA stages"
    )
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
            help_text=(
                "Two identical RC low-pass stages in series. Useful for post-lead spike absorption."
            ),
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

        stage1 = float(result[0])
        stage2 = stage1
        result[0] = stage2

        for i in range(1, result.size):
            x = float(result[i])
            stage1 = stage1 + alpha * (x - stage1)
            stage2 = stage2 + alpha * (stage1 - stage2)
            result[i] = stage2

        return result
