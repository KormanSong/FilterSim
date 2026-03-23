"""FFT 엔진 단위 테스트."""

import numpy as np
import pytest

from src.fft_engine import compute_fft


@pytest.fixture
def sine_50hz():
    """50Hz 단일 사인파 (fs=1000, 1000 samples)"""
    fs = 1000.0
    t = np.linspace(0, 1.0, int(fs), endpoint=False)
    data = np.sin(2 * np.pi * 50 * t)
    return data, fs


class TestComputeFFT:
    def test_peak_at_50hz(self, sine_50hz):
        """50Hz 입력 → peak frequency가 50Hz"""
        data, fs = sine_50hz
        freqs, mags = compute_fft(data, fs, "None")
        peak_idx = np.argmax(mags)
        assert freqs[peak_idx] == pytest.approx(50.0)

    def test_output_length(self, sine_50hz):
        """rfft 출력 길이 = n//2 + 1"""
        data, fs = sine_50hz
        freqs, mags = compute_fft(data, fs, "None")
        expected_len = len(data) // 2 + 1
        assert len(freqs) == expected_len
        assert len(mags) == expected_len

    def test_freq_range(self, sine_50hz):
        """주파수 범위: 0 ~ fs/2"""
        data, fs = sine_50hz
        freqs, mags = compute_fft(data, fs, "None")
        assert freqs[0] == pytest.approx(0.0)
        assert freqs[-1] == pytest.approx(fs / 2.0)

    def test_window_preserves_length(self, sine_50hz):
        """window 변경 시 배열 길이 유지"""
        data, fs = sine_50hz
        for window_name in ["None", "Hann", "Hamming", "Blackman"]:
            freqs, mags = compute_fft(data, fs, window_name)
            assert len(freqs) == len(data) // 2 + 1
            assert len(mags) == len(data) // 2 + 1

    def test_window_preserves_freq_axis(self, sine_50hz):
        """window 변경 시 주파수축 동일"""
        data, fs = sine_50hz
        freqs_none, _ = compute_fft(data, fs, "None")
        for window_name in ["Hann", "Hamming", "Blackman"]:
            freqs_w, _ = compute_fft(data, fs, window_name)
            np.testing.assert_array_equal(freqs_none, freqs_w)

    def test_coherent_gain_compensation(self, sine_50hz):
        """coherent gain 보정 후 peak 진폭이 window 간 일관됨"""
        data, fs = sine_50hz
        peaks = {}
        for window_name in ["None", "Hann", "Hamming", "Blackman"]:
            _, mags = compute_fft(data, fs, window_name)
            peaks[window_name] = np.max(mags)

        # 모든 window의 peak가 None 대비 ±10% 이내
        ref = peaks["None"]
        for name, peak in peaks.items():
            assert peak == pytest.approx(ref, rel=0.1), (
                f"{name}: peak={peak:.4f}, ref={ref:.4f}"
            )

    def test_peak_at_50hz_with_windows(self, sine_50hz):
        """모든 window에서 peak frequency가 50Hz"""
        data, fs = sine_50hz
        for window_name in ["Hann", "Hamming", "Blackman"]:
            freqs, mags = compute_fft(data, fs, window_name)
            peak_idx = np.argmax(mags)
            assert freqs[peak_idx] == pytest.approx(50.0), f"Failed for {window_name}"

    def test_short_data(self):
        """짧은 데이터 (1 sample) → 빈 배열"""
        freqs, mags = compute_fft(np.array([1.0]), 1000.0, "None")
        assert len(freqs) == 0
        assert len(mags) == 0

    def test_empty_data(self):
        """빈 데이터 → 빈 배열"""
        freqs, mags = compute_fft(np.array([]), 1000.0, "None")
        assert len(freqs) == 0
        assert len(mags) == 0

    def test_dc_offset_removed(self):
        """DC 오프셋이 있는 데이터 → DC 성분이 제거됨"""
        fs = 1000.0
        t = np.linspace(0, 1.0, int(fs), endpoint=False)
        # 큰 DC 오프셋 (400) + 작은 50Hz 사인파
        data = 400.0 + np.sin(2 * np.pi * 50 * t)
        freqs, mags = compute_fft(data, fs, "None")
        # DC (index 0)는 평균 제거 후 거의 0이어야 함
        assert mags[0] < 0.01
        # 50Hz peak는 여전히 검출
        peak_idx = np.argmax(mags)
        assert freqs[peak_idx] == pytest.approx(50.0)

    def test_dc_offset_peak_preserved(self):
        """DC 제거 후에도 신호 peak 진폭이 유지됨"""
        fs = 1000.0
        t = np.linspace(0, 1.0, int(fs), endpoint=False)
        # DC=0 vs DC=500, 동일 사인파
        sine = np.sin(2 * np.pi * 50 * t)
        _, mags_no_dc = compute_fft(sine, fs, "None")
        _, mags_with_dc = compute_fft(sine + 500.0, fs, "None")
        # 50Hz peak 진폭이 동일 (±1%)
        peak_no_dc = np.max(mags_no_dc)
        peak_with_dc = np.max(mags_with_dc)
        assert peak_with_dc == pytest.approx(peak_no_dc, rel=0.01)

    def test_dc_removed_with_all_windows(self):
        """모든 window에서 DC 오프셋이 제거됨 (window 가중평균 방식 검증)"""
        fs = 1000.0
        t = np.linspace(0, 1.0, int(fs), endpoint=False)
        data = 400.0 + np.sin(2 * np.pi * 50 * t)
        for window_name in ["None", "Hann", "Hamming", "Blackman"]:
            _, mags = compute_fft(data, fs, window_name)
            assert mags[0] < 0.01, (
                f"{window_name}: DC bin = {mags[0]:.4f}, expected < 0.01"
            )

    def test_dc_removed_with_windows_peak_preserved(self):
        """모든 window에서 DC 제거 후에도 50Hz peak 진폭 일관"""
        fs = 1000.0
        t = np.linspace(0, 1.0, int(fs), endpoint=False)
        sine = np.sin(2 * np.pi * 50 * t)
        data_with_dc = sine + 1000.0
        for window_name in ["Hann", "Hamming", "Blackman"]:
            _, mags_clean = compute_fft(sine, fs, window_name)
            _, mags_dc = compute_fft(data_with_dc, fs, window_name)
            peak_clean = np.max(mags_clean)
            peak_dc = np.max(mags_dc)
            assert peak_dc == pytest.approx(peak_clean, rel=0.02), (
                f"{window_name}: peak_dc={peak_dc:.4f}, peak_clean={peak_clean:.4f}"
            )

    def test_no_floor_in_engine(self):
        """compute_fft는 floor를 적용하지 않음 (원본 magnitude 반환)"""
        fs = 1000.0
        t = np.linspace(0, 1.0, int(fs), endpoint=False)
        # 순수 사인파 — DC 제거 후 DC bin은 매우 작아야 함
        data = np.sin(2 * np.pi * 50 * t)
        _, mags = compute_fft(data, fs, "None")
        # DC bin이 floor 없이 실제로 ~0에 가까워야 함 (1e-10 미만)
        assert mags[0] < 1e-10, f"DC bin = {mags[0]}, expected near zero without floor"
