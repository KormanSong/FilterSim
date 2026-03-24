"""평가 지표 계산 엔진 — UI 의존 없는 순수 계산 모듈.

모든 함수는 numpy 배열과 스칼라만 주고받으며,
Qt/PyQtGraph 의존이 없어 단위 테스트가 용이하다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class MetricsResult:
    """Raw/Filtered 비교 지표."""

    raw_settled_std: float
    filt_settled_std: float
    raw_hf_rms: float
    filt_hf_rms: float


def settled_std(data: NDArray[np.float64], start_idx: int, end_idx: int) -> float:
    """지정 구간 [start_idx, end_idx) 의 표준편차를 반환한다.

    Parameters
    ----------
    data : 1-D float64 배열
    start_idx : 구간 시작 인덱스 (포함)
    end_idx : 구간 끝 인덱스 (미포함)

    Returns
    -------
    표준편차 (구간이 2 미만이면 0.0)
    """
    if end_idx <= start_idx or data.size == 0:
        return 0.0
    start_idx = max(0, start_idx)
    end_idx = min(data.size, end_idx)
    segment = data[start_idx:end_idx]
    if segment.size < 2:
        return 0.0
    return float(np.std(segment, ddof=0))


def hf_rms(data: NDArray[np.float64], fs: float, cutoff_hz: float) -> float:
    """시간영역 1차 IIR 고역통과 적용 후 RMS를 반환한다.

    원본에서 1차 IIR 저역통과를 뺀 잔차의 RMS를 계산한다.
    (HPF = 원본 - LPF)

    이 방식은 FFT amplitude spectrum의 Parseval 불일치 문제를 회피하며,
    causal 1차 IIR이므로 MCU 펌웨어에서도 동일하게 측정 가능하다.

    Parameters
    ----------
    data : 1-D float64 배열
    fs : 샘플링 주파수 (Hz)
    cutoff_hz : 고역통과 차단 주파수 (Hz)

    Returns
    -------
    고주파 성분의 RMS (데이터가 2 미만이면 0.0)
    """
    if data.size < 2 or fs <= 0 or cutoff_hz <= 0:
        return 0.0

    # cutoff가 Nyquist 이상이면 통과 가능한 고주파 대역이 없다.
    if cutoff_hz >= fs / 2:
        return 0.0

    dt = 1.0 / fs
    rc = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)

    # 1차 IIR 저역통과: y[n] = y[n-1] + alpha * (x[n] - y[n-1])
    lpf = np.empty_like(data, dtype=np.float64)
    lpf[0] = data[0]
    for i in range(1, data.size):
        lpf[i] = lpf[i - 1] + alpha * (data[i] - lpf[i - 1])

    # 고역 = 원본 - 저역
    hf = data - lpf
    return float(np.sqrt(np.mean(hf * hf)))


def compute_metrics(
    raw: NDArray[np.float64],
    filtered: NDArray[np.float64],
    fs: float,
    cutoff_hz: float,
    start_idx: int,
    end_idx: int,
) -> MetricsResult:
    """Raw/Filtered 비교 지표를 일괄 계산한다.

    Parameters
    ----------
    raw : 원본 데이터
    filtered : 필터 적용 후 데이터
    fs : 샘플링 주파수
    cutoff_hz : HF RMS 차단 주파수
    start_idx : settled 구간 시작 인덱스
    end_idx : settled 구간 끝 인덱스
    """
    return MetricsResult(
        raw_settled_std=settled_std(raw, start_idx, end_idx),
        filt_settled_std=settled_std(filtered, start_idx, end_idx),
        raw_hf_rms=hf_rms(raw, fs, cutoff_hz),
        filt_hf_rms=hf_rms(filtered, fs, cutoff_hz),
    )
