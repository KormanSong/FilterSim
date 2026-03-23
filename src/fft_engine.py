"""FFT 계산 엔진 — rfft + window 적용 + coherent gain 보정."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# UI 콤보박스 문자열 → scipy window 이름 매핑
_WINDOW_MAP: dict[str, str | None] = {
    "None": None,        # rectangular (no window)
    "Hann": "hann",
    "Hamming": "hamming",
    "Blackman": "blackman",
}


def compute_fft(
    data: NDArray[np.float64],
    fs: float,
    window_name: str = "None",
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """one-sided FFT magnitude spectrum을 계산한다.

    Parameters
    ----------
    data : 1-D float64 배열
    fs : 샘플링 주파수 (Hz)
    window_name : UI 콤보박스 문자열 ("None", "Hann", "Hamming", "Blackman")

    Returns
    -------
    freqs : 주파수 배열 (0 ~ fs/2)
    magnitudes : coherent gain 보정된 진폭 스펙트럼 (floor 미적용 원본)

    Notes
    -----
    DC 제거: window별 가중평균을 사용한다.
      - rectangular (None): 산술평균 = sum(data)/n
      - 비직사각 window: 가중평균 = sum(w*data)/sum(w)
      이렇게 해야 sum(windowed) = 0이 보장되어 DC bin이 실제로 0에 수렴한다.

    coherent gain 보정: window 적용 시 peak 진폭이 줄어드는 것을 보상한다.
    보정 계수 = mean(window). 이를 나눠서 어떤 window를 선택하든
    단일 사인파의 peak 진폭이 일관되게 표시된다.
    """
    n = len(data)
    if n < 2:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    from scipy.fft import rfft, rfftfreq
    from scipy.signal import get_window

    # window 준비
    scipy_name = _WINDOW_MAP.get(window_name)
    if scipy_name is not None:
        w = get_window(scipy_name, n)
        coherent_gain = np.mean(w)
        # DC 제거 — window 가중평균을 빼서 sum(w * centered) = 0 보장
        weighted_mean = np.sum(w * data) / np.sum(w)
        windowed = (data - weighted_mean) * w
    else:
        coherent_gain = 1.0
        # DC 제거 — 산술평균 (rectangular window)
        windowed = data - np.mean(data)

    # rfft → magnitude
    spectrum = rfft(windowed)
    magnitudes = np.abs(spectrum) / n  # 정규화
    # one-sided: DC와 Nyquist를 제외한 성분은 2배
    if n > 1:
        magnitudes[1:-1] *= 2.0

    # coherent gain 보정
    if coherent_gain > 0:
        magnitudes = magnitudes / coherent_gain

    freqs = rfftfreq(n, d=1.0 / fs)

    return freqs, magnitudes
