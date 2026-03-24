"""Moving Average 필터 — 현재 샘플과 과거값만 쓰는 causal average."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.signal_context import SignalContext
from src.filters.base import BaseFilter, ParamSpec


class MovingAverageFilter(BaseFilter):
    name = "이동평균 (MA)"
    description = "Causal moving average using current and past samples only"
    params_spec = (
        ParamSpec(
            name="window_size",
            label="Window Size",
            type="int",
            default=20,
            min=1,
            max=5000,
            step=1,
            unit="samples",
            help_text="Past-only moving average. Example: MA240 at 1 kHz gives ~119.5 ms delay.",
        ),
    )

    def estimated_delay_samples(
        self, ctx: SignalContext, **params: Any
    ) -> float | None:
        p = self.validate_params(ctx, **params)
        window_size: int = p["window_size"]
        return (window_size - 1) / 2.0

    def apply(
        self, data: NDArray[np.float64], ctx: SignalContext, **params: Any
    ) -> NDArray[np.float64]:
        p = self.validate_params(ctx, **params)
        window_size: int = p["window_size"]

        if data.size == 0:
            return data.astype(np.float64, copy=True)

        values = data.astype(np.float64, copy=False)
        kernel = np.ones(window_size, dtype=np.float64)
        summed = np.convolve(values, kernel, mode="full")[: values.size]
        counts = np.minimum(np.arange(1, values.size + 1), window_size)
        return summed / counts
