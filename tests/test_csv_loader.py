"""CSV loader and time-axis validation tests."""

from pathlib import Path

import numpy as np
import pytest

from src.csv_loader import load_columns, read_headers, validate_time_axis


def test_read_headers_filters_unnamed_columns(tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("time,data,Unnamed: 2\n0.0,1.0,\n", encoding="utf-8")

    headers = read_headers(csv_path)

    assert headers == ["time", "data"]


def test_load_columns_pairwise_drops_invalid_rows(tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "time,data\n"
        "0.0,1.0\n"
        "0.1,foo\n"
        "bar,3.0\n"
        "0.3,4.0\n",
        encoding="utf-8",
    )

    time_arr, data_arr, n_total, n_valid = load_columns(csv_path, "time", "data")

    assert n_total == 4
    assert n_valid == 2
    np.testing.assert_allclose(time_arr, np.array([0.0, 0.3]))
    np.testing.assert_allclose(data_arr, np.array([1.0, 4.0]))


def test_validate_time_axis_allows_duplicate_timestamps():
    time_arr = np.array([0.0, 0.001, 0.002, 0.002, 0.003], dtype=np.float64)

    ctx = validate_time_axis(time_arr, n_total=5, n_valid=5)

    assert ctx.fs == pytest.approx(1000.0)
    assert ctx.is_uniform is True


def test_validate_time_axis_allows_sparse_duplicate_timestamps():
    time_arr = np.arange(1000, dtype=np.float64) / 1000.0
    time_arr = np.insert(time_arr, 500, time_arr[500])

    ctx = validate_time_axis(time_arr, n_total=len(time_arr), n_valid=len(time_arr))

    assert ctx.fs == pytest.approx(1000.0)
    assert ctx.is_uniform is True


def test_validate_time_axis_small_jitter_is_treated_as_uniform():
    base = np.arange(1000, dtype=np.float64) / 1000.0
    jitter = np.zeros_like(base)
    jitter[1:] = np.sin(np.arange(999, dtype=np.float64)) * 1e-6
    time_arr = base + jitter

    ctx = validate_time_axis(time_arr, n_total=len(time_arr), n_valid=len(time_arr))

    assert ctx.fs == pytest.approx(1000.0)
    assert ctx.is_uniform is True


def test_validate_time_axis_rejects_negative_intervals():
    time_arr = np.array([0.0, 0.001, 0.003, 0.002], dtype=np.float64)

    with pytest.raises(ValueError, match="monotonically non-decreasing"):
        validate_time_axis(time_arr, n_total=4, n_valid=4)


def test_validate_time_axis_regular_series_returns_expected_context():
    time_arr = np.arange(1000, dtype=np.float64) / 1000.0

    ctx = validate_time_axis(time_arr, n_total=1000, n_valid=1000)

    assert ctx.fs == pytest.approx(1000.0)
    assert ctx.dt == pytest.approx(0.001)
    assert ctx.is_uniform is True
    assert ctx.n_total == 1000
    assert ctx.n_valid == 1000
