"""Lead Compensator filter for OriginalAD -> iFilteredAdSensor path."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.filters.base import BaseFilter, ParamSpec
from src.signal_context import SignalContext

_MICRO_TO_BASE = 1e-6


class LeadCompensatorFilter(BaseFilter):
    name = "미분 필터"
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

    def startup_discard_samples(
        self, ctx: SignalContext, data_len: int, **params: Any
    ) -> int:
        self.validate_params(ctx, **params)
        if data_len <= 0:
            return 0
        return 1

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

        # H(z) = [(1+Ka) - a(1+K)z^{-1}] / [1 - az^{-1}]
        from scipy.signal import lfilter

        K = kr_coeff1
        b = np.array([1.0 + K * a, -a * (1.0 + K)])
        a_coeff = np.array([1.0, -a])
        zi = np.array([-K * a * float(result[0])])
        result, _ = lfilter(b, a_coeff, result, zi=zi)

        return np.asarray(result, dtype=np.float64)
