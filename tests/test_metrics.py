"""평가 지표 엔진 단위 테스트."""

import numpy as np
import pytest

from src.metrics_engine import settled_std, hf_rms, compute_metrics


# ── settled_std ──────────────────────────────────────────


def test_settled_std_known_value():
    """알려진 std를 가진 구간 → 정확한 값 반환."""
    data = np.array([10.0, 12.0, 8.0, 10.0, 12.0, 8.0], dtype=np.float64)
    # 전체 std(ddof=0)
    expected = float(np.std(data, ddof=0))
    result = settled_std(data, 0, len(data))
    assert abs(result - expected) < 1e-10


def test_settled_std_partial_region():
    """후반 구간만 지정 → 해당 구간의 std만 계산."""
    data = np.array([100.0, 200.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
    # 인덱스 2~6 구간: [1, 1, 1, 1] → std = 0
    result = settled_std(data, 2, 6)
    assert result == 0.0


def test_settled_std_empty():
    """빈 배열 → 0.0."""
    data = np.array([], dtype=np.float64)
    assert settled_std(data, 0, 0) == 0.0


def test_settled_std_single_element():
    """단일 요소 → 0.0."""
    data = np.array([5.0], dtype=np.float64)
    assert settled_std(data, 0, 1) == 0.0


def test_settled_std_out_of_bounds_clamped():
    """범위 초과 인덱스 → 클램프하여 계산."""
    data = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    result = settled_std(data, -5, 100)
    expected = float(np.std(data, ddof=0))
    assert abs(result - expected) < 1e-10


# ── hf_rms ───────────────────────────────────────────────


def test_hf_rms_pure_dc():
    """순수 DC 신호 → HF RMS ≈ 0."""
    data = np.full(1000, 5.0, dtype=np.float64)
    result = hf_rms(data, fs=1000.0, cutoff_hz=50.0)
    assert result < 0.01


def test_hf_rms_pure_high_freq():
    """cutoff 이상 주파수만 있는 신호 → HF RMS > 0."""
    fs = 1000.0
    t = np.arange(2000) / fs
    # 200 Hz 사인파 (cutoff=50Hz 이상)
    data = np.sin(2 * np.pi * 200 * t).astype(np.float64)
    result = hf_rms(data, fs=fs, cutoff_hz=50.0)
    # 사인파 RMS ≈ 1/sqrt(2) ≈ 0.707, 1차 HPF 통과 후 대부분 통과
    assert result > 0.5


def test_hf_rms_low_freq_below_cutoff():
    """cutoff 이하 저주파만 있는 신호 → HF RMS 작음."""
    fs = 1000.0
    t = np.arange(5000) / fs
    # 2 Hz 사인파 (cutoff=50Hz 이하)
    data = np.sin(2 * np.pi * 2 * t).astype(np.float64)
    result = hf_rms(data, fs=fs, cutoff_hz=50.0)
    # 1차 HPF가 대부분 차단 → 작은 값
    assert result < 0.15


def test_hf_rms_empty():
    """빈 배열 → 0.0."""
    data = np.array([], dtype=np.float64)
    assert hf_rms(data, fs=1000.0, cutoff_hz=50.0) == 0.0


def test_hf_rms_invalid_params():
    """잘못된 파라미터 → 0.0."""
    data = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    assert hf_rms(data, fs=0.0, cutoff_hz=50.0) == 0.0
    assert hf_rms(data, fs=1000.0, cutoff_hz=0.0) == 0.0


def test_hf_rms_at_nyquist_returns_zero():
    """Nyquist에서 통과 가능한 고주파 대역이 없으므로 0.0."""
    fs = 1000.0
    t = np.arange(5000) / fs
    data = np.sin(2 * np.pi * 2 * t).astype(np.float64)
    assert hf_rms(data, fs=fs, cutoff_hz=fs / 2.0) == 0.0


def test_hf_rms_above_nyquist_returns_zero():
    """Nyquist 초과 cutoff도 0.0으로 처리."""
    fs = 1000.0
    t = np.arange(5000) / fs
    data = np.sin(2 * np.pi * 200 * t).astype(np.float64)
    assert hf_rms(data, fs=fs, cutoff_hz=fs) == 0.0


# ── compute_metrics ──────────────────────────────────────


def test_compute_metrics_noise_reduction():
    """노이즈 제거 필터 적용 후 → settled std, HF RMS 모두 감소."""
    rng = np.random.default_rng(42)
    fs = 1000.0
    n = 5000
    clean = np.full(n, 100.0, dtype=np.float64)
    noise = rng.normal(0, 5.0, n)
    raw = clean + noise

    # 단순 이동평균 필터 시뮬레이션 (window=50)
    kernel = np.ones(50) / 50.0
    filtered = np.convolve(raw, kernel, mode="same").astype(np.float64)

    result = compute_metrics(
        raw, filtered, fs=fs, cutoff_hz=50.0,
        start_idx=n - n // 5, end_idx=n,
    )

    # 필터 후 settled std가 줄어야 함
    assert result.filt_settled_std < result.raw_settled_std
    # 필터 후 HF RMS가 줄어야 함
    assert result.filt_hf_rms < result.raw_hf_rms


def test_compute_metrics_dc_preserved():
    """DC 오프셋 → settled std가 DC에 영향받지 않음."""
    n = 1000
    data_a = np.full(n, 100.0, dtype=np.float64)
    data_b = np.full(n, 500.0, dtype=np.float64)

    # 동일 노이즈 없는 DC → std ≈ 0
    result = compute_metrics(data_a, data_b, fs=1000.0, cutoff_hz=50.0, start_idx=800, end_idx=1000)
    assert result.raw_settled_std < 0.01
    assert result.filt_settled_std < 0.01
