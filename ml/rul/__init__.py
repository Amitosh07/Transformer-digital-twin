"""Versioned synthetic RUL and evidence-only operational eligibility."""
from .config import Duty, SyntheticConfig
from .model import RULProjection, assess_operational_eligibility, first_passage, operational_result, predict_synthetic
__all__=['Duty','SyntheticConfig','RULProjection','assess_operational_eligibility','first_passage','operational_result','predict_synthetic']
