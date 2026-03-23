"""필터 레지스트리 — 새 필터 추가 시 여기에 1줄만 등록."""

from src.filters.base import BaseFilter
from src.filters.moving_average import MovingAverageFilter
from src.filters.median import MedianFilter
from src.filters.fir import FIRFilter
from src.filters.iir_lpf import IIRLowpassFilter
from src.filters.biquad_lowpass import BesselLowpassFilter
from src.filters.lead_compensator import LeadCompensatorFilter

FILTER_REGISTRY: dict[str, type[BaseFilter]] = {
    "Moving Average": MovingAverageFilter,
    "Median": MedianFilter,
    "FIR": FIRFilter,
    "IIR Lowpass": IIRLowpassFilter,
    "Bessel Lowpass (2nd)": BesselLowpassFilter,
    "Lead Compensator": LeadCompensatorFilter,
}
