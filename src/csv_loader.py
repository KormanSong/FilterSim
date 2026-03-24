from pathlib import Path

import numpy as np
import pandas as pd

from src.signal_context import SignalContext

# 균일성 판정: 대표 dt 대비 상대 표준편차 허용치
_UNIFORMITY_TOLERANCE = 0.05


def read_headers(path: str | Path) -> list[str]:
    """CSV 헤더만 읽어 유효한 컬럼 이름 리스트를 반환한다.

    - nrows=0 으로 헤더 행만 파싱
    - 빈 문자열 및 'Unnamed' 컬럼(trailing comma 등) 제거
    """
    df = pd.read_csv(path, nrows=0)
    return [
        col for col in df.columns
        if col.strip() and not col.startswith("Unnamed")
    ]


def load_columns(
    path: str | Path, time_col: str, data_col: str
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """선택된 두 열만 읽고, 숫자 변환 + pairwise drop 후 반환한다.

    Returns:
        (time_array, data_array, n_total, n_valid)
    """
    df = pd.read_csv(path, usecols=[time_col, data_col])
    n_total = len(df)

    df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
    df[data_col] = pd.to_numeric(df[data_col], errors="coerce")
    df = df.dropna()
    n_valid = len(df)

    return df[time_col].to_numpy(), df[data_col].to_numpy(), n_total, n_valid


def validate_time_axis(
    time_array: np.ndarray, n_total: int, n_valid: int
) -> SignalContext:
    """시간축을 검증하고 SignalContext를 생성한다.

    사전 조건:
      - 시간축은 비감소(monotonic non-decreasing)해야 함
      - time_span > 0, dt_median > 0 이어야 함

    균일성 판정:
      양의 dt들의 대표값(중앙값) 대비 상대 표준편차로 판정한다.
      양자화 노이즈(CSV 소수점 해상도 한계)에 강건하며,
      중복 timestamp(dt=0)는 대표 dt 계산에서 제외한다.
    """
    dt_array = np.diff(time_array)

    # 단조 비감소 검증: logging artifact로 생긴 duplicate timestamp(dt=0)는 허용한다.
    if np.any(dt_array < 0):
        n_negative = int(np.sum(dt_array < 0))
        raise ValueError(
            "Time column must be monotonically non-decreasing "
            f"({n_negative:,} negative interval(s) found). "
            "Please select the correct Time column."
        )

    dt_positive = dt_array[dt_array > 0]
    if len(dt_positive) == 0:
        raise ValueError("All time intervals are zero - cannot determine sampling rate.")
    dt_median = np.median(dt_positive)
    dt_std = np.std(dt_positive, ddof=0)
    relative_std = float(dt_std / dt_median) if dt_median > 0 else float("inf")

    # 전체 구간 기반
    time_span = time_array[-1] - time_array[0]
    n = len(time_array)
    fs_span = (n - 1) / time_span

    # 대표 dt 기반
    fs_median = 1.0 / dt_median

    # 상대 표준편차가 충분히 작으면 균일 샘플링으로 간주하고 대표 dt를 사용한다.
    is_uniform = bool(relative_std < _UNIFORMITY_TOLERANCE)
    fs_estimate = fs_median if is_uniform else fs_span

    # 반올림된 운영 fs
    fs = round(fs_estimate)
    if fs <= 0:
        raise ValueError(f"Computed sampling frequency is invalid (fs={fs}).")

    return SignalContext(
        fs=float(fs),
        dt=1.0 / fs,
        is_uniform=is_uniform,
        n_total=n_total,
        n_valid=n_valid,
    )
