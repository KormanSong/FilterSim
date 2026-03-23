"""FilterChain 단위 테스트."""

import numpy as np
import pytest

from src.signal_context import SignalContext
from src.filter_chain import FilterChain
from src.filters.moving_average import MovingAverageFilter
from src.filters.median import MedianFilter
from src.filters.fir import FIRFilter
from src.filters.iir_lpf import IIRLowpassFilter
from src.filters.biquad_lowpass import BesselLowpassFilter
from src.filters.lead_compensator import LeadCompensatorFilter
from src.filters import FILTER_REGISTRY


@pytest.fixture
def ctx():
    return SignalContext(fs=1000.0, dt=0.001, is_uniform=True, n_total=500, n_valid=500)


@pytest.fixture
def data():
    t = np.linspace(0, 0.5, 500, endpoint=False)
    return np.sin(2 * np.pi * 50 * t) + np.random.randn(500) * 0.1


class TestFilterChain:
    def test_empty_chain_returns_copy(self, ctx, data):
        chain = FilterChain()
        result = chain.execute(data, ctx)
        np.testing.assert_array_equal(result, data.astype(np.float64))
        assert result is not data  # 복사본이어야 함

    def test_single_filter(self, ctx, data):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        result = chain.execute(data, ctx)
        assert len(result) == len(data)
        assert np.std(result) < np.std(data)

    def test_chain_order_matters(self, ctx, data):
        chain1 = FilterChain()
        chain1.add(MovingAverageFilter(), {"window_size": 11})
        chain1.add(MedianFilter(), {"kernel_size": 5})
        result1 = chain1.execute(data, ctx)

        chain2 = FilterChain()
        chain2.add(MedianFilter(), {"kernel_size": 5})
        chain2.add(MovingAverageFilter(), {"window_size": 11})
        result2 = chain2.execute(data, ctx)

        # 순서가 다르면 결과도 달라야 함
        assert not np.allclose(result1, result2)

    def test_disabled_filter_skipped(self, ctx, data):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        chain.set_enabled(0, False)
        result = chain.execute(data, ctx)
        np.testing.assert_array_equal(result, data.astype(np.float64))

    def test_add_returns_index(self):
        chain = FilterChain()
        idx0 = chain.add(MovingAverageFilter(), {"window_size": 5})
        idx1 = chain.add(MedianFilter(), {"kernel_size": 3})
        assert idx0 == 0
        assert idx1 == 1

    def test_remove(self):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        chain.add(MedianFilter(), {"kernel_size": 3})
        assert len(chain) == 2
        chain.remove(0)
        assert len(chain) == 1
        assert chain.entries[0].filter_instance.name == "Median"

    def test_move(self):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        chain.add(MedianFilter(), {"kernel_size": 3})
        chain.move(1, 0)
        assert chain.entries[0].filter_instance.name == "Median"
        assert chain.entries[1].filter_instance.name == "Moving Average"

    def test_set_params(self, ctx, data):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        result1 = chain.execute(data, ctx)

        chain.set_params(0, {"window_size": 21})
        result2 = chain.execute(data, ctx)

        # 다른 파라미터 → 다른 결과
        assert not np.allclose(result1, result2)

    def test_clear(self):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        chain.add(MedianFilter(), {"kernel_size": 3})
        chain.clear()
        assert len(chain) == 0

    def test_float64_output(self, ctx):
        """int 입력도 float64로 변환"""
        data_int = np.array([1, 2, 3, 4, 5, 4, 3, 2, 1] * 50)
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 3})
        result = chain.execute(data_int, ctx)
        assert result.dtype == np.float64

    def test_registry_has_three_filters(self):
        assert len(FILTER_REGISTRY) == 6
        assert "Moving Average" in FILTER_REGISTRY
        assert "Median" in FILTER_REGISTRY
        assert "FIR" in FILTER_REGISTRY
        assert "IIR Lowpass" in FILTER_REGISTRY
        assert "Bessel Lowpass (2nd)" in FILTER_REGISTRY
        assert "Lead Compensator" in FILTER_REGISTRY

    def test_iir_lowpass_in_chain(self, ctx, data):
        chain = FilterChain()
        chain.add(IIRLowpassFilter(), {})
        result = chain.execute(data, ctx)
        assert len(result) == len(data)
        assert result.dtype == np.float64
        assert np.std(result) < np.std(data)

    def test_lead_compensator_in_chain(self, ctx, data):
        chain = FilterChain()
        chain.add(LeadCompensatorFilter(), {"kr_coeff1": 1.0})
        result = chain.execute(data, ctx)
        assert len(result) == len(data)
        assert result.dtype == np.float64

    def test_bessel_lowpass_in_chain(self, ctx, data):
        chain = FilterChain()
        chain.add(BesselLowpassFilter(), {"cutoff_hz": 20.0})
        result = chain.execute(data, ctx)
        assert len(result) == len(data)
        assert result.dtype == np.float64

    def test_delay_estimate_for_causal_moving_average(self, ctx):
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 240})
        delay_samples, has_known, has_unknown = chain.estimate_delay_samples(ctx)
        assert delay_samples == pytest.approx(119.5)
        assert has_known is True
        assert has_unknown is False

    def test_delay_estimate_for_iir_is_unknown(self, ctx):
        chain = FilterChain()
        chain.add(IIRLowpassFilter(), {})
        delay_samples, has_known, has_unknown = chain.estimate_delay_samples(ctx)
        assert delay_samples == pytest.approx(0.0)
        assert has_known is False
        assert has_unknown is True

    def test_delay_estimate_for_fir_is_known(self, ctx):
        chain = FilterChain()
        chain.add(FIRFilter(), {"mode": "lowpass", "cutoff_low": 50.0, "numtaps": 101})
        delay_samples, has_known, has_unknown = chain.estimate_delay_samples(ctx)
        assert delay_samples == pytest.approx(50.0)
        assert has_known is True
        assert has_unknown is False

    def test_entries_is_readonly_snapshot(self):
        """entries 반환값을 변조해도 내부 상태에 영향 없음"""
        chain = FilterChain()
        chain.add(MovingAverageFilter(), {"window_size": 5})
        snapshot = chain.entries
        assert isinstance(snapshot, tuple)
        assert len(chain) == 1
        # tuple은 clear()가 없으므로 직접 변조 불가
