"""Lead Compensator filter for OriginalAD -> iFilteredAdSensor path."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.filters.base import BaseFilter, ParamSpec
from src.signal_context import SignalContext

_MICRO_TO_BASE = 1e-6


class LeadCompensatorFilter(BaseFilter):
    name = "Lead Compensator"
    description = "Discrete lead compensator using g_rKrCoeff1 and RC time constant"
    params_spec = (
        ParamSpec(
            name="kr_coeff1",
            label="Gain (g_rKrCoeff1)",
            type="float",
            default=135.0,
            min=0.0,
            max=10000.0,
            step=1.0,
        ),
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
            default=33.0,
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
        kr_coeff1: float = p["kr_coeff1"]
        resistor_ohms: float = p["resistor_ohms"]
        capacitor_uf: float = p["capacitor_uf"]

        if ctx.dt <= 0:
            raise ValueError(f"{self.name}: ctx.dt must be positive, got {ctx.dt}")

        result = data.astype(np.float64, copy=True)
        if result.size == 0:
            return result

        rc_seconds = resistor_ohms * capacitor_uf * _MICRO_TO_BASE
        a = rc_seconds / (rc_seconds + ctx.dt)

        prev_sensor_diff = 0.0
        prev_original = float(result[0])

        for i, original in enumerate(result):
            sensor_diff = a * (prev_sensor_diff + original - prev_original)
            result[i] = original + kr_coeff1 * sensor_diff
            prev_sensor_diff = sensor_diff
            prev_original = original

        return result
