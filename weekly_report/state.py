from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field


# -------- Raw input layer --------


class SleepStageMinutes(BaseModel):
    total_sleep_minutes: Optional[float] = None
    in_bed_minutes: Optional[float] = None
    deep_sleep_minutes: Optional[float] = None
    rem_sleep_minutes: Optional[float] = None
    core_sleep_minutes: Optional[float] = None
    sleep_efficiency_score: Optional[float] = Field(
        None, description="Optional raw sleep score from provider (0-100)."
    )


class HRVSnapshot(BaseModel):
    hrv_rmssd_today: Optional[float] = None
    hrv_rmssd_3day_avg: Optional[float] = None
    hrv_rmssd_7day_avg: Optional[float] = None
    hrv_rmssd_28day_avg: Optional[float] = None
    hrv_rmssd_28day_sd: Optional[float] = None
    device: Optional[str] = None


class TrainingSessionInput(BaseModel):
    label: Optional[str] = Field(
        None, description="训练标签（无/低/中/高/极高或更精细的客户端标签）"
    )
    rpe: Optional[float] = None
    duration_minutes: Optional[float] = None
    au: Optional[float] = Field(
        None, description="如果客户端已计算 AU，可直接提供"
    )
    start_time: Optional[str] = None
    notes: Optional[str] = None


class HooperScores(BaseModel):
    fatigue: Optional[int] = None
    soreness: Optional[int] = None
    stress: Optional[int] = None
    sleep: Optional[int] = None


class JournalFlags(BaseModel):
    alcohol_consumed: Optional[bool] = None
    late_caffeine: Optional[bool] = None
    screen_before_bed: Optional[bool] = None
    late_meal: Optional[bool] = None
    is_sick: Optional[bool] = None
    is_injured: Optional[bool] = None
    lifestyle_tags: Optional[Sequence[str]] = Field(
        None,
        description="结构化生活方式标签，例如 high_stress_day、travel_day。",
    )
    sliders: Optional[Dict[str, float]] = Field(
        None, description="滑杆类签到数据，例如疲劳滑杆、情绪状态等。"
    )


class BodyMetrics(BaseModel):
    bodyweight_kg: Optional[float] = None
    bodyfat_pct: Optional[float] = None
    resting_hr: Optional[float] = None


class RawInputs(BaseModel):
    user_id: Optional[str] = None
    date: Optional[str] = None
    gender: Optional[str] = None
    sleep: SleepStageMinutes = SleepStageMinutes()
    hrv: HRVSnapshot = HRVSnapshot()
    training_sessions: List[TrainingSessionInput] = Field(default_factory=list)
    hooper: HooperScores = HooperScores()
    journal: JournalFlags = JournalFlags()
    body_metrics: BodyMetrics = BodyMetrics()
    external_events: Optional[Sequence[str]] = Field(
        None, description="重要事件或脚本无法识别的快速备注。"
    )
    report_notes: Optional[str] = Field(
        None,
        description="用于周报/LLM 的自由文本日志，不参与传统 readiness 计算。",
    )


# -------- Deterministic metrics layer --------


class TrainingLoadMetrics(BaseModel):
    daily_au_28d: Optional[List[float]] = None
    daily_au_7d: Optional[List[float]] = None
    acwr_value: Optional[float] = None
    acwr_band: Optional[str] = None
    acute_load: Optional[float] = None
    chronic_load: Optional[float] = None
    consecutive_high_days: Optional[int] = None
    training_volume: Optional[float] = None
    training_intensity_index: Optional[float] = None


class RecoveryMetrics(BaseModel):
    sleep_efficiency: Optional[float] = None
    sleep_restorative_ratio: Optional[float] = None
    sleep_duration_hours: Optional[float] = None
    sleep_duration_delta: Optional[float] = Field(
        None, description="与基线或目标睡眠时长的差值（小时）。"
    )
    css_score: Optional[float] = None


class PhysiologicalMetrics(BaseModel):
    hrv_z_score: Optional[float] = None
    hrv_trend: Optional[str] = None
    hrv_state: Optional[str] = None
    readiness_prior: Optional[Dict[str, float]] = None


class SubjectiveMetrics(BaseModel):
    hooper_bands: Optional[Dict[str, str]] = None
    doms_score: Optional[float] = None
    energy_score: Optional[float] = None
    fatigue_score: Optional[float] = Field(
        None, description="综合 DOMS/能量/近期 AU 的疲劳指数。"
    )


class BaselineMetrics(BaseModel):
    sleep_baseline_hours: Optional[float] = None
    sleep_baseline_efficiency: Optional[float] = None
    rest_baseline_ratio: Optional[float] = None
    hrv_mu: Optional[float] = None
    hrv_sigma: Optional[float] = None
    personalized_thresholds: Dict[str, float] = Field(default_factory=dict)


class StrengthMetrics(BaseModel):
    e1rm_estimates: Optional[Dict[str, float]] = None
    velocity_loss_pct: Optional[float] = None


class Metrics(BaseModel):
    training_load: TrainingLoadMetrics = TrainingLoadMetrics()
    recovery: RecoveryMetrics = RecoveryMetrics()
    physiology: PhysiologicalMetrics = PhysiologicalMetrics()
    subjective: SubjectiveMetrics = SubjectiveMetrics()
    baselines: BaselineMetrics = BaselineMetrics()
    strength: StrengthMetrics = StrengthMetrics()


# -------- Trend & long-horizon layer --------


class TrendPoint(BaseModel):
    date: str
    value: Optional[float] = None
    label: Optional[str] = None


class TrendSeries(BaseModel):
    name: str
    points: List[TrendPoint] = Field(default_factory=list)
    window_days: Optional[int] = None
    notes: Optional[str] = None


class TrendMetadata(BaseModel):
    weekly_delta: Optional[float] = None
    monthly_delta: Optional[float] = None
    slope: Optional[float] = None
    phase: Optional[str] = Field(
        None, description="训练周期阶段：accumulation / transmutation / realization 等。"
    )
    confidence: Optional[float] = Field(
        None, description="0-1 范围，用于表示趋势置信度。"
    )


class TrendBundle(BaseModel):
    series: Dict[str, TrendSeries] = Field(default_factory=dict)
    metadata: Dict[str, TrendMetadata] = Field(default_factory=dict)


# -------- Insights layer --------


class InsightEvidence(BaseModel):
    key: str
    value: Optional[float] = None
    description: Optional[str] = None


class InsightAction(BaseModel):
    recommendation: str
    category: Optional[str] = Field(
        None, description="e.g. training_adjustment / recovery / lifestyle"
    )
    priority: Optional[int] = Field(
        None, description="1=highest priority；数值越大优先级越低。"
    )


class InsightItem(BaseModel):
    id: str
    trigger: str
    summary: str
    explanation: str
    actions: List[InsightAction] = Field(default_factory=list)
    evidence: List[InsightEvidence] = Field(default_factory=list)
    confidence: Optional[float] = None
    tags: Optional[Sequence[str]] = None


# -------- Report payload layer --------


class ChartSpec(BaseModel):
    chart_id: str
    title: str
    chart_type: str = Field(
        ..., description="ECharts 类型：line、bar、radar 等。"
    )
    data: Dict[str, object] = Field(
        default_factory=dict, description="直接可供前端渲染的 ECharts 配置。"
    )
    notes: Optional[str] = None


class ReportSummary(BaseModel):
    readiness_score: Optional[float] = None
    readiness_band: Optional[str] = None
    drivers: List[str] = Field(
        default_factory=list,
        description="核心驱动因素摘要，例如 ['高训练负荷', '睡眠不足']。",
    )
    opportunities: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class ReportMetadata(BaseModel):
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    data_sources: List[str] = Field(default_factory=list)
    data_quality_score: Optional[float] = None
    generated_at: Optional[str] = None
    generator_version: Optional[str] = None


class ReportPayload(BaseModel):
    summary: ReportSummary = ReportSummary()
    charts: List[ChartSpec] = Field(default_factory=list)
    insights: List[str] = Field(
        default_factory=list, description="适用于直接渲染的洞察摘要文本。"
    )
    metadata: ReportMetadata = ReportMetadata()


# -------- Top-level state --------


class ReadinessState(BaseModel):
    raw_inputs: RawInputs = RawInputs()
    metrics: Metrics = Metrics()
    trends: TrendBundle = TrendBundle()
    insights: List[InsightItem] = Field(default_factory=list)
    insight_reviews: List[Dict[str, Any]] = Field(default_factory=list)
    report_payload: ReportPayload = ReportPayload()
    # 可选：下周训练计划（由 Planner 规则生成，Phase 3B）。不强耦合具体模型，避免循环依赖。
    next_week_plan: Optional[Any] = None


__all__ = [
    "ReadinessState",
    "RawInputs",
    "Metrics",
    "TrendBundle",
    "InsightItem",
    "ReportPayload",
]
