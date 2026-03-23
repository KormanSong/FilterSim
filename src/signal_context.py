from dataclasses import dataclass


@dataclass
class SignalContext:
    """신호 컨텍스트 — 필터와 FFT가 공통으로 사용하는 운영값.

    fs: 반올림된 샘플링 주파수 (Hz)
    dt: 1/fs (운영값, 실측값 아님)
    is_uniform: 시간축 균일 여부
    n_total: CSV 원본 행 수 (헤더 제외)
    n_valid: 유효 행 수 (NaN pairwise drop 후)
    """
    fs: float
    dt: float
    is_uniform: bool
    n_total: int
    n_valid: int
