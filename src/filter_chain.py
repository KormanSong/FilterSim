"""필터 체인 파이프라인 엔진."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.signal_context import SignalContext
from src.filters.base import BaseFilter


@dataclass
class ChainEntry:
    """체인 내 필터 하나의 상태."""
    filter_instance: BaseFilter
    params: dict[str, Any]
    enabled: bool = True


class FilterChain:
    """필터를 순서대로 직렬 적용하는 파이프라인."""

    def __init__(self) -> None:
        self._entries: list[ChainEntry] = []

    @property
    def entries(self) -> tuple[ChainEntry, ...]:
        """읽기 전용 스냅샷. 내부 리스트를 직접 변조할 수 없다."""
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, filter_instance: BaseFilter, params: dict[str, Any]) -> int:
        """필터를 체인 끝에 추가하고 인덱스를 반환한다."""
        entry = ChainEntry(filter_instance=filter_instance, params=params)
        self._entries.append(entry)
        return len(self._entries) - 1

    def remove(self, index: int) -> None:
        """인덱스 위치의 필터를 제거한다."""
        del self._entries[index]

    def move(self, from_index: int, to_index: int) -> None:
        """필터를 from_index에서 to_index로 이동한다."""
        entry = self._entries.pop(from_index)
        self._entries.insert(to_index, entry)

    def set_enabled(self, index: int, enabled: bool) -> None:
        """인덱스 위치 필터의 활성 상태를 변경한다."""
        self._entries[index].enabled = enabled

    def set_params(self, index: int, params: dict[str, Any]) -> None:
        """인덱스 위치 필터의 파라미터를 변경한다."""
        self._entries[index].params = params

    def clear(self) -> None:
        """체인의 모든 필터를 제거한다."""
        self._entries.clear()

    def estimate_delay_samples(self, ctx: SignalContext) -> tuple[float, bool, bool]:
        """활성 필터 체인의 근사 지연 샘플 수를 집계한다.

        반환:
          (total_delay_samples, has_known_delay, has_unknown_delay)
        """
        total = 0.0
        has_known = False
        has_unknown = False

        for entry in self._entries:
            if not entry.enabled:
                continue
            delay = entry.filter_instance.estimated_delay_samples(ctx, **entry.params)
            if delay is None:
                has_unknown = True
            else:
                total += float(delay)
                has_known = True

        return total, has_known, has_unknown

    def estimate_startup_discard_samples(
        self, ctx: SignalContext, data_len: int
    ) -> int:
        """활성 필터 체인의 초기 warm-up discard 샘플 수를 집계한다."""
        total = 0

        for entry in self._entries:
            if not entry.enabled:
                continue
            total += int(
                entry.filter_instance.startup_discard_samples(
                    ctx, data_len, **entry.params
                )
            )

        return max(0, min(data_len, total))

    def execute(self, data: NDArray, ctx: SignalContext) -> NDArray[np.float64]:
        """활성화된 필터를 순서대로 적용하고 결과를 반환한다.

        입력은 float64로 캐스팅되어 일관된 dtype을 보장한다.
        """
        result = data.astype(np.float64, copy=True)
        for entry in self._entries:
            if entry.enabled:
                result = entry.filter_instance.apply(result, ctx, **entry.params)
        return result
