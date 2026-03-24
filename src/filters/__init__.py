"""필터 레지스트리 — 새 필터 추가 시 여기에 1줄만 등록."""

from src.filters.base import BaseFilter
from src.filters.moving_average import MovingAverageFilter
from src.filters.median import MedianFilter
from src.filters.fir import FIRFilter
from src.filters.iir_lpf import IIRLowpassFilter
from src.filters.biquad_lowpass import BesselLowpassFilter
from src.filters.critical_damped_lpf import CriticalDampedLowpassFilter
from src.filters.lead_compensator import LeadCompensatorFilter

FILTER_REGISTRY: dict[str, type[BaseFilter]] = {
    "FIR": FIRFilter,
    "미분 필터": LeadCompensatorFilter,
    "이동평균 (MA)": MovingAverageFilter,
    "Median": MedianFilter,
    "IIR LPF": IIRLowpassFilter,
    "IIR LPF (2차)": CriticalDampedLowpassFilter,
    "Bessel LPF (2nd)": BesselLowpassFilter,
}
