"""Median 필터 — 현재 샘플과 과거값만 쓰는 causal median."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.signal_context import SignalContext
from src.filters.base import BaseFilter, ParamSpec


class MedianFilter(BaseFilter):
    name = "Median"
    description = "Causal sliding median using current and past samples only"
    params_spec = (
        ParamSpec(
            name="kernel_size",
            label="Kernel Size",
            type="int",
            default=5,
            min=3,
            max=501,
            step=2,
            unit="samples",
            constraint="odd",
            help_text="Past-only median. Effective delay is approximately kernel_size // 2 samples.",
        ),
    )

    def estimated_delay_samples(
        self, ctx: SignalContext, **params: Any
    ) -> float | None:
        p = self.validate_params(ctx, **params)
        kernel_size: int = p["kernel_size"]
        return float(kernel_size // 2)

    def apply(
        self, data: NDArray[np.float64], ctx: SignalContext, **params: Any
    ) -> NDArray[np.float64]:
        from scipy.ndimage import median_filter

        p = self.validate_params(ctx, **params)
        kernel_size: int = p["kernel_size"]

        # origin=kernel_size//2 로 윈도우를 과거 방향으로 밀어 causal median처럼 사용한다.
        # mode='nearest'는 시작 구간에서 첫 샘플을 유지해 미래 샘플 참조를 피한다.
        result = median_filter(
            data,
            size=kernel_size,
            mode="nearest",
            origin=kernel_size // 2,
        )
        return result.astype(np.float64)
