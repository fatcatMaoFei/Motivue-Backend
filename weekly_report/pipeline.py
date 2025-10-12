from __future__ import annotations

import logging
from typing import Optional, Sequence

from readiness.llm.provider import LLMCallError, LLMProvider, get_llm_provider
from weekly_report.models import (
    AnalystOpportunity,
    AnalystReport,
    AnalystRisk,
    ChartSpec,
    CommunicatorReport,
    CommunicatorSection,
    ReportCritique,
    WeeklyHistoryEntry,
    WeeklyReportPackage,
)
from weekly_report.trend_builder import build_default_chart_specs
from readiness.state import InsightItem, ReadinessState

logger = logging.getLogger(__name__)


def generate_weekly_report(
    state: ReadinessState,
    history: Sequence[WeeklyHistoryEntry],
    *,
    sleep_baseline_hours: Optional[float] = None,
    hrv_baseline: Optional[float] = None,
    provider: Optional[LLMProvider] = None,
) -> WeeklyReportPackage:
    """Generate charts + LLM summary + communicator draft for Phase 4."""

    charts = build_default_chart_specs(
        history, sleep_baseline_hours=sleep_baseline_hours, hrv_baseline=hrv_baseline
    )
    report_notes = state.raw_inputs.report_notes

    llm = provider or get_llm_provider()
    analyst: AnalystReport
    communicator: CommunicatorReport
    critique: ReportCritique = _fallback_critique()

    if llm is not None:
        try:
            analyst = llm.generate_weekly_analyst(
                state, charts, report_notes=report_notes
            )
        except LLMCallError as exc:
            logger.warning("Weekly analyst LLM failed, fallback to heuristic: %s", exc)
            analyst = _fallback_analyst(state, charts)
            communicator = _fallback_communicator(state, analyst)
            critique = _fallback_critique()
        else:
            try:
                communicator = llm.generate_weekly_communicator(
                    state,
                    analyst,
                    charts,
                    report_notes=report_notes,
                )
            except LLMCallError as exc:
                logger.warning(
                    "Weekly communicator LLM failed, fallback to heuristic: %s", exc
                )
                communicator = _fallback_communicator(state, analyst)
            else:
                try:
                    critique = llm.generate_weekly_report_critique(
                        analyst, communicator, charts
                    )
                except LLMCallError as exc:
                    logger.warning(
                        "Weekly critique LLM failed, returning communicator draft as-is: %s",
                        exc,
                    )
    else:
        logger.info("LLM provider unavailable; using heuristic weekly report.")
        analyst = _fallback_analyst(state, charts)
        communicator = _fallback_communicator(state, analyst)

    return WeeklyReportPackage(
        charts=list(charts),
        analyst=analyst,
        communicator=communicator,
        critique=critique if critique.issues else None,
    )


# -------- Fallback heuristics -------- #


def _fallback_analyst(
    state: ReadinessState, charts: Sequence[ChartSpec]
) -> AnalystReport:
    insights = [item for item in state.insights if isinstance(item, InsightItem)]
    summary_points = [ins.summary for ins in insights[:3]]
    if not summary_points:
        summary_points = [
            "整体维持在可控区间，建议持续监测 HRV 与睡眠趋势。",
        ]

    risks: list[AnalystRisk] = []
    for ins in insights:
        tags = set(ins.tags or [])
        if any(tag in {"risk", "training_load", "recovery"} for tag in tags) or "风险" in ins.summary:
            risks.append(
                AnalystRisk(
                    metric=ins.trigger,
                    value=None,
                    reason=ins.explanation,
                    severity="medium",
                )
            )
    if not risks and insights:
        risks = [
            AnalystRisk(
                metric=insights[0].trigger,
                value=None,
                reason=insights[0].explanation,
                severity="medium",
            )
        ]

    opportunities: list[AnalystOpportunity] = []
    for ins in insights:
        if ins.actions:
            for act in ins.actions[:2]:
                opportunities.append(
                    AnalystOpportunity(
                        area=act.category or ins.trigger,
                        recommendation=act.recommendation,
                        reason=ins.summary,
                    )
                )
    if not opportunities and insights:
        opportunities.append(
            AnalystOpportunity(
                area="恢复策略",
                recommendation="保持高质量睡眠并安排一次主动恢复训练。",
                reason="暂无明确行动项，建议维持良好作息。",
            )
        )

    return AnalystReport(
        summary_points=summary_points,
        risks=risks[:3],
        opportunities=opportunities[:3],
        chart_ids=[chart.chart_id for chart in charts[:4]],
    )


def _fallback_communicator(
    state: ReadinessState, analyst: AnalystReport
) -> CommunicatorReport:
    positive_lines = analyst.summary_points or [
        "整体状态稳定，请继续保持良好的训练与恢复节奏。"
    ]
    risk_lines = [f"- {risk.metric}: {risk.reason}" for risk in analyst.risks[:3]]
    if not risk_lines:
        risk_lines = ["- 暂无显著风险，继续保持监测。"]
    opportunity_lines = [
        f"- {opp.area}: {opp.recommendation}"
        for opp in analyst.opportunities[:3]
    ]
    if not opportunity_lines:
        opportunity_lines = ["- 维持现有恢复安排，关注高质量睡眠。"]

    sections = [
        CommunicatorSection(
            title="本周亮点",
            body_markdown="\n".join(f"- {line}" for line in positive_lines),
        ),
        CommunicatorSection(
            title="风险观察",
            body_markdown="\n".join(risk_lines),
        ),
        CommunicatorSection(
            title="建议与行动",
            body_markdown="\n".join(opportunity_lines),
        ),
    ]
    call_to_action = [
        analyst.opportunities[0].recommendation
        for analyst in [analyst]
        if analyst.opportunities
    ]
    if not call_to_action:
        call_to_action = ["保持规律睡眠，维持当前训练与恢复节奏。"]

    return CommunicatorReport(
        sections=sections,
        tone="professional_encouraging",
        call_to_action=call_to_action,
    )


# Critique fallback：若 LLM 不可用，则认为草稿可接受，返回空 issues。


def _fallback_critique() -> ReportCritique:
    return ReportCritique(issues=[])
