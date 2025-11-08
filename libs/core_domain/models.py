from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field


class ChartSpec(BaseModel):
    """Generic chart specification payload (ECharts/前端可直接消费)."""

    chart_id: str = Field(..., description="Chart unique identifier.")
    title: str = Field(..., description="Human readable chart title.")
    chart_type: str = Field(..., description="e.g. line, bar, radar, pie.")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Front-end ready chart options/data."
    )
    notes: Optional[str] = Field(
        None, description="Optional textual note or insight for the chart."
    )


class WeeklyHistoryEntry(BaseModel):
    """Minimal历史数据条目，用于构建周报趋势/图表."""

    date: date
    readiness_score: Optional[float] = Field(
        None,
        description="每日准备度分数（final_readiness_score 或 current_readiness_score）。",
    )
    readiness_band: Optional[str] = Field(
        None, description="准备度分档：Peak/Well-adapted/FOR/Acute Fatigue/NFOR/OTS 等。"
    )
    hrv_rmssd: Optional[float] = None
    hrv_z_score: Optional[float] = None
    sleep_duration_hours: Optional[float] = None
    sleep_total_minutes: Optional[float] = None
    sleep_deep_minutes: Optional[float] = None
    sleep_rem_minutes: Optional[float] = None
    daily_au: Optional[float] = None
    acwr: Optional[float] = None
    hooper: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Hooper 四项评分，键建议为 fatigue/soreness/stress/sleep。",
    )
    lifestyle_events: Sequence[str] = Field(
        default_factory=tuple, description="任意生活方式标签数组。"
    )


class AnalystRisk(BaseModel):
    metric: str = Field(..., description="风险关注的指标或项目。")
    value: Optional[str] = Field(
        None, description="相关数值或状态，如 1.45 或 '下降'。"
    )
    reason: str = Field(..., description="风险成立的原因或证据。")
    severity: Optional[str] = Field(
        None, description="可选：low/medium/high，便于排序或着色。"
    )


class AnalystOpportunity(BaseModel):
    area: str = Field(..., description="机会领域，例如 恢复/训练质量。")
    recommendation: str = Field(..., description="可执行的改进行动。")
    reason: Optional[str] = Field(None, description="补充说明或数据支持。")


class AnalystReport(BaseModel):
    summary_points: List[str] = Field(
        default_factory=list, description="本周关键观察/亮点。"
    )
    risks: List[AnalystRisk] = Field(
        default_factory=list, description="需要警惕的风险列表。"
    )
    opportunities: List[AnalystOpportunity] = Field(
        default_factory=list, description="潜在提升机会。"
    )
    chart_ids: List[str] = Field(
        default_factory=list,
        description="建议重点展示的图表 ID 列表（来自 chart_specs）。",
    )


class CommunicatorSection(BaseModel):
    title: str = Field(..., description="报告段落标题。")
    body_markdown: str = Field(..., description="Markdown 正文内容。")


class CommunicatorReport(BaseModel):
    sections: List[CommunicatorSection] = Field(
        default_factory=list, description="报告段落列表。"
    )
    tone: Optional[str] = Field(
        None, description="报告语气，例如 professional_encouraging。"
    )
    call_to_action: List[str] = Field(
        default_factory=list, description="明确的行动项或提醒。"
    )


class ReportIssue(BaseModel):
    sentence: str = Field(..., description="存在问题的句子/段落。")
    reason: str = Field(..., description="问题原因或不准确之处。")
    fix: str = Field(..., description="建议的修正方式。")


class ReportCritique(BaseModel):
    issues: List[ReportIssue] = Field(
        default_factory=list, description="批注问题列表；空数组表示无问题。"
    )
    overall_feedback: Optional[str] = Field(
        None, description="可选：总体评价或下一步建议。"
    )


class WeeklyReportPackage(BaseModel):
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="生成时间（UTC）。"
    )
    charts: List[ChartSpec]
    analyst: AnalystReport
    communicator: CommunicatorReport
    critique: Optional[ReportCritique] = None


class WeeklyFinalReport(BaseModel):
    """最终输出给前端/教练端的完整周报."""

    markdown_report: str = Field(..., description="完整 Markdown 文本。")
    html_report: Optional[str] = Field(
        None, description="可选：Markdown 转换后的 HTML。"
    )
    chart_ids: List[str] = Field(
        default_factory=list, description="推荐展示的图表 ID 顺序。"
    )
    call_to_action: List[str] = Field(
        default_factory=list, description="明确的行动项列表。"
    )


__all__ = [
    "ChartSpec",
    "WeeklyHistoryEntry",
    "AnalystRisk",
    "AnalystOpportunity",
    "AnalystReport",
    "CommunicatorSection",
    "CommunicatorReport",
    "ReportIssue",
    "ReportCritique",
    "WeeklyReportPackage",
    "WeeklyFinalReport",
]
