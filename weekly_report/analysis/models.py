from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DailyRootCause(BaseModel):
    date: date
    readiness_score: Optional[float] = None
    readiness_band: Optional[str] = None
    drivers: List[str] = Field(default_factory=list, description="Key factors contributing to low readiness")


class LoadImpactSummary(BaseModel):
    high_acwr_days: int = 0
    high_acwr_ratio: Optional[float] = None
    low_acwr_days: int = 0
    consecutive_high_runs: int = 0
    avg_next_day_readiness_delta: Optional[float] = None
    avg_next_day_hrv_delta: Optional[float] = None
    avg_readiness_drop_after_streak: Optional[float] = None
    avg_hrv_drop_after_streak: Optional[float] = None
    correlation_readiness: Optional[float] = None
    correlation_hrv: Optional[float] = None


class SleepImpactSummary(BaseModel):
    correlation_readiness: Optional[float] = None
    correlation_hrv: Optional[float] = None
    restorative_correlation_readiness: Optional[float] = None
    restorative_correlation_hrv: Optional[float] = None
    low_sleep_days: int = 0
    low_restorative_days: int = 0
    avg_readiness_drop: Optional[float] = None
    avg_hrv_drop: Optional[float] = None
    avg_readiness_drop_after_low_rest: Optional[float] = None
    avg_hrv_drop_after_low_rest: Optional[float] = None


class LifestyleImpact(BaseModel):
    event: str
    occurrences: int
    avg_readiness_delta: Optional[float] = None
    avg_hrv_delta: Optional[float] = None
    avg_sleep_delta: Optional[float] = None
    notes: Optional[str] = None


class SubjectiveObjectiveConflictSummary(BaseModel):
    subjective_high_objective_stable: int = 0
    subjective_low_objective_low: int = 0
    stress_conflicts: int = 0
    sleep_quality_conflicts: int = 0
    details: Dict[str, List[date]] = Field(default_factory=dict)


class RecoveryResponseSummary(BaseModel):
    average_recovery_ratio: Optional[float] = None
    slow_recovery_cases: int = 0
    avg_readiness_rebound: Optional[float] = None
    avg_sleep_rebound: Optional[float] = None
    avg_sleep_rebound_vs_baseline: Optional[float] = None
    notes: Optional[str] = None


class TrendStabilitySummary(BaseModel):
    readiness_slope: Optional[float] = None
    hrv_slope: Optional[float] = None
    sleep_slope: Optional[float] = None
    readiness_volatility: Optional[float] = None
    hrv_volatility: Optional[float] = None
    sleep_volatility: Optional[float] = None
    readiness_change: Optional[float] = None
    hrv_vs_baseline: Optional[float] = None
    sleep_vs_baseline: Optional[float] = None


class AnalysisBundle(BaseModel):
    root_causes: List[DailyRootCause] = Field(default_factory=list)
    load_impact: LoadImpactSummary = LoadImpactSummary()
    sleep_impact: SleepImpactSummary = SleepImpactSummary()
    lifestyle_impacts: List[LifestyleImpact] = Field(default_factory=list)
    subjective_objective_conflicts: SubjectiveObjectiveConflictSummary = SubjectiveObjectiveConflictSummary()
    recovery_response: RecoveryResponseSummary = RecoveryResponseSummary()
    trend_stability: TrendStabilitySummary = TrendStabilitySummary()
