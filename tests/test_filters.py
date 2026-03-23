"""필터 단위 테스트."""

import numpy as np
import pytest

from src.signal_context import SignalContext
from src.filters.moving_average import MovingAverageFilter
from src.filters.median import MedianFilter
from src.filters.fir import FIRFilter
from src.filters.iir_lpf import IIRLowpassFilter
from src.filters.biquad_lowpass import BesselLowpassFilter
from src.filters.lead_compensator import LeadCompensatorFilter


@pytest.fixture
def ctx():
    return SignalContext(fs=1000.0, dt=0.001, is_uniform=True, n_total=1000, n_valid=1000)


@pytest.fixture
def sine_data():
    """50Hz + 200Hz 합성 사인파 (1000 samples, fs=1000)"""
    t = np.linspace(0, 1.0, 1000, endpoint=False)
    return np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 200 * t)


@pytest.fixture
def short_data():
    """짧은 데이터 (8 samples)"""
    return np.array([1.0, 2.0, 3.0, 4.0, 5.0, 4.0, 3.0, 2.0])


# ── Moving Average ──────────────────────────────

class TestMovingAverage:
    def test_output_length(self, ctx, sine_data):
        f = MovingAverageFilter()
        result = f.apply(sine_data, ctx, window_size=11)
        assert len(result) == len(sine_data)

    def test_no_edge_spike(self, ctx, sine_data):
        f = MovingAverageFilter()
        result = f.apply(sine_data, ctx, window_size=11)
        assert result.max() <= sine_data.max() + 0.1
        assert result.min() >= sine_data.min() - 0.1

    def test_smoothing_effect(self, ctx, sine_data):
        f = MovingAverageFilter()
        result = f.apply(sine_data, ctx, window_size=21)
        assert np.std(result) < np.std(sine_data)

    def test_even_window_is_allowed(self, ctx, sine_data):
        f = MovingAverageFilter()
        result = f.apply(sine_data, ctx, window_size=10)
        assert len(result) == len(sine_data)

    def test_invalid_below_min(self, ctx, sine_data):
        f = MovingAverageFilter()
        with pytest.raises(ValueError, match="below minimum"):
            f.apply(sine_data, ctx, window_size=0)

    def test_is_causal_past_only_average(self, ctx):
        data = np.concatenate([np.zeros(10), np.ones(10)])
        f = MovingAverageFilter()
        result = f.apply(data, ctx, window_size=4)
        assert result[9] == pytest.approx(0.0)
        assert result[10] == pytest.approx(0.25)
        assert result[11] == pytest.approx(0.5)
        assert result[12] == pytest.approx(0.75)
        assert result[13] == pytest.approx(1.0)

    def test_delay_estimate_for_ma240(self, ctx):
        f = MovingAverageFilter()
        assert f.estimated_delay_samples(ctx, window_size=240) == pytest.approx(119.5)


# ── Median ──────────────────────────────────────

class TestMedian:
    def test_output_length(self, ctx, sine_data):
        f = MedianFilter()
        result = f.apply(sine_data, ctx, kernel_size=5)
        assert len(result) == len(sine_data)

    def test_no_edge_spike(self, ctx, sine_data):
        f = MedianFilter()
        result = f.apply(sine_data, ctx, kernel_size=5)
        assert result.max() <= sine_data.max() + 0.01
        assert result.min() >= sine_data.min() - 0.01

    def test_spike_removal(self, ctx):
        """중간에 스파이크가 있는 데이터 → median으로 제거"""
        data = np.ones(100)
        data[50] = 100.0  # spike
        f = MedianFilter()
        result = f.apply(data, ctx, kernel_size=3)
        assert result[50] == 1.0  # spike 제거됨

    def test_float64_output(self, ctx, sine_data):
        f = MedianFilter()
        result = f.apply(sine_data, ctx, kernel_size=5)
        assert result.dtype == np.float64

    def test_is_causal_past_only_median(self, ctx):
        data = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        f = MedianFilter()
        result = f.apply(data, ctx, kernel_size=5)
        np.testing.assert_allclose(result, np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0]))


# ── FIR ─────────────────────────────────────────

class TestFIR:
    def test_lowpass_length(self, ctx, sine_data):
        f = FIRFilter()
        result = f.apply(sine_data, ctx, mode="lowpass", cutoff_low=100.0, numtaps=51)
        assert len(result) == len(sine_data)

    def test_highpass_length(self, ctx, sine_data):
        f = FIRFilter()
        result = f.apply(sine_data, ctx, mode="highpass", cutoff_high=100.0, numtaps=51)
        assert len(result) == len(sine_data)

    def test_bandpass_length(self, ctx, sine_data):
        f = FIRFilter()
        result = f.apply(
            sine_data, ctx, mode="bandpass",
            cutoff_low=30.0, cutoff_high=80.0, numtaps=51
        )
        assert len(result) == len(sine_data)

    def test_lowpass_attenuates_high_freq(self, ctx, sine_data):
        """50Hz + 200Hz 신호에 100Hz lowpass → 200Hz 성분 감소"""
        f = FIRFilter()
        result = f.apply(sine_data, ctx, mode="lowpass", cutoff_low=100.0, numtaps=101)
        assert np.std(result) < np.std(sine_data)

    def test_causal_step_response_has_visible_delay(self, ctx):
        data = np.concatenate([np.zeros(20), np.ones(80)])
        f = FIRFilter()
        result = f.apply(data, ctx, mode="lowpass", cutoff_low=20.0, numtaps=21)
        assert result[20] < 0.2
        assert result[30] > result[20]

    def test_short_data_returns_copy(self, ctx, short_data):
        """< 10 samples → 원본 복사 반환"""
        f = FIRFilter()
        result = f.apply(short_data, ctx, mode="lowpass", cutoff_low=100.0, numtaps=101)
        np.testing.assert_array_equal(result, short_data)

    def test_medium_data_numtaps_reduction(self, ctx):
        """30 samples → numtaps 자동 축소"""
        data = np.random.randn(30)
        f = FIRFilter()
        result = f.apply(data, ctx, mode="lowpass", cutoff_low=100.0, numtaps=101)
        assert len(result) == 30

    def test_invalid_cutoff_above_nyquist(self, ctx, sine_data):
        f = FIRFilter()
        with pytest.raises(ValueError, match="above maximum"):
            f.apply(sine_data, ctx, mode="lowpass", cutoff_low=600.0, numtaps=51)

    def test_invalid_bandpass_order(self, ctx, sine_data):
        f = FIRFilter()
        with pytest.raises(ValueError, match="must be <"):
            f.apply(
                sine_data, ctx, mode="bandpass",
                cutoff_low=200.0, cutoff_high=100.0, numtaps=51
            )

    def test_dynamic_params_spec(self, ctx):
        f = FIRFilter()
        specs = f.get_params_spec(ctx)
        cutoff_specs = {s.name: s for s in specs}
        assert cutoff_specs["cutoff_low"].max == pytest.approx(499.9)
        assert cutoff_specs["cutoff_high"].max == pytest.approx(499.9)

    def test_default_params(self, ctx):
        f = FIRFilter()
        defaults = f.default_params(ctx)
        assert defaults["mode"] == "lowpass"
        assert defaults["numtaps"] == 101

    def test_lowfs_highpass_hidden_cutoff_low(self):
        """fs=60 → highpass에서 cutoff_low(기본값 50)가 숨김 처리되어 검증 통과"""
        ctx_low = SignalContext(fs=60.0, dt=1/60, is_uniform=True, n_total=100, n_valid=100)
        data = np.random.randn(100)
        f = FIRFilter()
        # cutoff_high=10 < nyquist(30), cutoff_low는 숨김 → 기본값 50이어도 통과해야 함
        result = f.apply(data, ctx_low, mode="highpass", cutoff_high=10.0, numtaps=11)
        assert len(result) == 100

    def test_lowfs_lowpass_hidden_cutoff_high(self):
        """fs=60 → lowpass에서 cutoff_high(기본값 200)가 숨김 처리되어 검증 통과"""
        ctx_low = SignalContext(fs=60.0, dt=1/60, is_uniform=True, n_total=100, n_valid=100)
        data = np.random.randn(100)
        f = FIRFilter()
        result = f.apply(data, ctx_low, mode="lowpass", cutoff_low=10.0, numtaps=11)
        assert len(result) == 100

    def test_default_params_clamp_low_fs(self):
        """fs=60 → default cutoff_low(50) 및 cutoff_high(200) clamp 확인"""
        ctx_low = SignalContext(fs=60.0, dt=1/60, is_uniform=True, n_total=100, n_valid=100)
        f = FIRFilter()
        defaults = f.default_params(ctx_low)
        nyquist_limit = 60.0 / 2.0 - 0.1
        assert defaults["cutoff_low"] <= nyquist_limit
        assert defaults["cutoff_high"] <= nyquist_limit

    def test_default_params_no_clamp_high_fs(self, ctx):
        """fs=1000 → 기본값 유지 (clamp 불필요)"""
        f = FIRFilter()
        defaults = f.default_params(ctx)
        assert defaults["cutoff_low"] == 50.0
        assert defaults["cutoff_high"] == 200.0

    def test_unknown_param_raises(self, ctx, sine_data):
        """알 수 없는 파라미터 키 → ValueError"""
        f = FIRFilter()
        with pytest.raises(ValueError, match="unknown parameter"):
            f.apply(sine_data, ctx, mode="lowpass", cutoff_low=50.0, numtaps=51, typo=123)

    def test_delay_estimate_matches_numtaps(self, ctx):
        f = FIRFilter()
        assert f.estimated_delay_samples(ctx, mode="lowpass", cutoff_low=50.0, numtaps=101) == pytest.approx(50.0)


# ── Lead Compensator ─────────────────────────────

class TestIIRLowpass:
    def test_output_length(self, ctx, sine_data):
        f = IIRLowpassFilter()
        result = f.apply(sine_data, ctx)
        assert len(result) == len(sine_data)

    def test_constant_signal_passthrough(self, ctx):
        data = np.full(128, 12.5)
        f = IIRLowpassFilter()
        result = f.apply(data, ctx)
        np.testing.assert_allclose(result, data)

    def test_step_response_is_smoothed(self, ctx):
        data = np.concatenate([np.zeros(10), np.ones(40)])
        f = IIRLowpassFilter()
        result = f.apply(data, ctx)
        assert result[10] < 1.0
        assert np.all(np.diff(result[10:]) >= -1e-12)
        assert result[-1] > 0.9

    def test_high_frequency_is_attenuated_more_than_low_frequency(self, ctx):
        t = np.linspace(0, 1.0, 1000, endpoint=False)
        low = np.sin(2 * np.pi * 5 * t)
        high = np.sin(2 * np.pi * 100 * t)
        f = IIRLowpassFilter()

        low_filtered = f.apply(low, ctx)
        high_filtered = f.apply(high, ctx)

        low_gain = np.std(low_filtered) / np.std(low)
        high_gain = np.std(high_filtered) / np.std(high)
        assert low_gain > high_gain

    def test_invalid_capacitor_below_min(self, ctx, sine_data):
        f = IIRLowpassFilter()
        with pytest.raises(ValueError, match="below minimum"):
            f.apply(sine_data, ctx, capacitor_uf=0.0)


# ── 2nd-Order Lowpass ───────────────────────────

class TestBesselLowpass:
    def test_output_length(self, ctx, sine_data):
        f = BesselLowpassFilter()
        result = f.apply(sine_data, ctx, cutoff_hz=20.0)
        assert len(result) == len(sine_data)

    def test_constant_signal_passthrough(self, ctx):
        data = np.full(128, 12.5)
        f = BesselLowpassFilter()
        result = f.apply(data, ctx, cutoff_hz=20.0)
        np.testing.assert_allclose(result, data, atol=1e-9)

    def test_high_frequency_is_attenuated_more_than_low_frequency(self, ctx):
        t = np.linspace(0, 1.0, 1000, endpoint=False)
        low = np.sin(2 * np.pi * 5 * t)
        high = np.sin(2 * np.pi * 100 * t)
        f = BesselLowpassFilter()

        low_filtered = f.apply(low, ctx, cutoff_hz=20.0)
        high_filtered = f.apply(high, ctx, cutoff_hz=20.0)

        low_gain = np.std(low_filtered) / np.std(low)
        high_gain = np.std(high_filtered) / np.std(high)
        assert low_gain > high_gain

    def test_step_response_has_low_overshoot(self, ctx):
        data = np.concatenate([np.zeros(100), np.ones(900)])
        result = BesselLowpassFilter().apply(data, ctx, cutoff_hz=20.0)
        overshoot = float(np.max(result) - 1.0)
        assert overshoot <= 0.02


# ── Lead Compensator ─────────────────────────────

class TestLeadCompensator:
    def test_output_length(self, ctx, sine_data):
        f = LeadCompensatorFilter()
        result = f.apply(sine_data, ctx)
        assert len(result) == len(sine_data)

    def test_constant_signal_passthrough(self, ctx):
        data = np.full(128, 7.0)
        f = LeadCompensatorFilter()
        result = f.apply(data, ctx)
        np.testing.assert_allclose(result, data)

    def test_zero_gain_returns_input(self, ctx, sine_data):
        f = LeadCompensatorFilter()
        result = f.apply(sine_data, ctx, kr_coeff1=0.0)
        np.testing.assert_allclose(result, sine_data)

    def test_step_response_has_lead_effect(self, ctx):
        data = np.concatenate([np.zeros(10), np.ones(20)])
        f = LeadCompensatorFilter()
        result = f.apply(
            data,
            ctx,
            kr_coeff1=1.0,
            resistor_ohms=1000.0,
            capacitor_uf=33.0,
        )
        assert result[10] > data[10]

    def test_invalid_capacitor_below_min(self, ctx, sine_data):
        f = LeadCompensatorFilter()
        with pytest.raises(ValueError, match="below minimum"):
            f.apply(sine_data, ctx, capacitor_uf=0.0)
