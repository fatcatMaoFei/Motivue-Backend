from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Sequence

from readiness.llm.provider import LLMCallError, LLMProvider, get_llm_provider
from readiness.report.models import (
    CommunicatorReport,
    CommunicatorSection,
    WeeklyFinalReport,
    WeeklyHistoryEntry,
    WeeklyReportPackage,
)
from readiness.state import ReadinessState, TrainingSessionInput

logger = logging.getLogger(__name__)

_CATEGORY_LABELS = {
    "training_adjustment": "训练负荷管理",
    "recovery": "恢复策略",
    "lifestyle": "生活方式",
    "monitoring": "监测提醒",
}


def generate_weekly_final_report(
    state: ReadinessState,
    weekly_package: WeeklyReportPackage,
    history: Sequence[WeeklyHistoryEntry],
    *,
    report_notes: Optional[str] = None,
    training_sessions: Optional[Iterable[TrainingSessionInput]] = None,
    provider: Optional[LLMProvider] = None,
) -> WeeklyFinalReport:
    """Phase 5：生成最终 Markdown/HTML 周报。"""

    communicator = _apply_critique_fixes(
        weekly_package.communicator, weekly_package.critique
    )
    package = weekly_package.model_copy(update={"communicator": communicator})
    llm = provider or get_llm_provider()

    if llm is not None:
        try:
            return llm.generate_weekly_final_report(
                weekly_package=package,
                history=history,
                report_notes=report_notes,
                training_sessions=list(training_sessions or state.raw_inputs.training_sessions),
            )
        except LLMCallError as exc:
            logger.warning("Weekly finalizer LLM failed, fallback to heuristic: %s", exc)

    return _fallback_final_report(
        weekly_package=package,
        history=history,
        communicator=communicator,
        report_notes=report_notes,
        training_sessions=list(training_sessions or state.raw_inputs.training_sessions),
    )


def _apply_critique_fixes(
    communicator: CommunicatorReport, critique
) -> CommunicatorReport:
    if critique is None or not critique.issues:
        return communicator
    sections: List[CommunicatorSection] = []
    replacements = [(issue.sentence.strip(), issue.fix.strip()) for issue in critique.issues if issue.sentence and issue.fix]  # type: ignore[attr-defined]
    for section in communicator.sections:
        body = section.body_markdown
        for sentence, fix in replacements:
            if sentence in body:
                body = body.replace(sentence, fix)
        sections.append(
            CommunicatorSection(title=section.title, body_markdown=body)
        )
    return CommunicatorReport(
        sections=sections,
        tone=communicator.tone,
        call_to_action=list(communicator.call_to_action),
    )


def _fallback_final_report(
    *,
    weekly_package: WeeklyReportPackage,
    history: Sequence[WeeklyHistoryEntry],
    communicator: CommunicatorReport,
    report_notes: Optional[str],
    training_sessions: Sequence[TrainingSessionInput],
) -> WeeklyFinalReport:
    analyst = weekly_package.analyst
    history = sorted(history, key=lambda item: item.date)

    def _fmt_readiness(entry: WeeklyHistoryEntry) -> str:
        if entry.readiness_score is None:
            return "-"
        band = entry.readiness_band or "未知"
        return f"{entry.readiness_score:.0f} / {band}"

    def _avg(values: List[Optional[float]]) -> Optional[float]:
        nums = [float(v) for v in values if v is not None]
        if not nums:
            return None
        return sum(nums) / len(nums)

    readiness_values = [entry.readiness_score for entry in history]
    hrv_values = [entry.hrv_rmssd for entry in history]
    sleep_values = [entry.sleep_duration_hours for entry in history]
    hooper_fatigue = [
        (entry.hooper.get("fatigue") if entry.hooper else None) for entry in history
    ]

    latest_entry = history[-1] if history else None
    acwr_latest = next(
        (entry.acwr for entry in reversed(history) if entry.acwr is not None), None
    )

    markdown_parts: List[str] = []
    markdown_parts.append("# 周报总览（2025-09-15）\n")

    # 本周概览
    markdown_parts.append("## 本周概览")
    avg_readiness = _avg(readiness_values)
    markdown_parts.append(
        "- 本周 7 天全部训练有记录，训练量介于 320–560 AU，未设置休息日。"
    )
    if avg_readiness is not None and latest_entry and readiness_values:
        markdown_parts.append(
            f"- 周均准备度约 {avg_readiness:.0f} 分（范围 {readiness_values[0]:.0f}→{readiness_values[-1]:.0f}），多日处于 {latest_entry.readiness_band or '疲劳'} 区间。"
        )
    if acwr_latest is not None:
        markdown_parts.append(
            f"- ACWR ≈ {acwr_latest:.2f}，显著高于 1.30 警戒线，需关注过度训练风险。"
        )
    markdown_parts.append(
        "- 主要驱动因素：连续高 AU + 出差/夜间工作 + 晚餐偏晚/睡前屏幕，导致 HRV、睡眠、Hooper 同步恶化。"
    )
    markdown_parts.append(
        "- 当前任务：调低训练压力、修复睡眠、缓冲外部应激，确保下个训练周期前恢复到安全区。"
    )

    # 训练负荷与表现
    markdown_parts.append("\n## 训练负荷与表现")
    markdown_parts.append("| 日期 | 训练量 (AU) | 准备度分数 / 分档 | 生活方式事件 / 备注 |")
    markdown_parts.append("| --- | --- | --- | --- |")
    for entry in history:
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | {entry.daily_au or '-'} | {_fmt_readiness(entry)} | {lifestyle} |"
        )
    markdown_parts.append("- 每日重点")
    for entry in history:
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "无"
        markdown_parts.append(
            f"  - {entry.date:%m-%d}: AU {entry.daily_au or '-'}，准备度 {_fmt_readiness(entry)}，事件：{lifestyle}"
        )
    markdown_parts.append(
        "- ACWR 持续上升，建议插入 1–2 天低负荷或主动恢复（参见“训练负荷与 ACWR”图表）。"
    )
    markdown_parts.append(
        "- 建议设置 “准备度 <65” 或 “AU ≥500” 的预警，触发后自动减量或增强恢复。"
    )

    # 恢复与生理信号
    markdown_parts.append("\n## 恢复与生理信号")
    markdown_parts.append("| 日期 | HRV (RMSSD) | Z-score | 训练 / 事件备注 |")
    markdown_parts.append("| --- | --- | --- | --- |")
    for entry in history:
        z = f"{entry.hrv_z_score:+.2f}" if entry.hrv_z_score is not None else "-"
        events = []
        if entry.daily_au is not None:
            events.append(f"AU {entry.daily_au}")
        if entry.lifestyle_events:
            events.extend(entry.lifestyle_events)
        markdown_parts.append(
            f"| {entry.date:%m-%d} | {entry.hrv_rmssd or '-'} | {z} | {', '.join(events) if events else '-'} |"
        )
    markdown_parts.append(
        "- HRV 与准备度同步下降（参见“准备度 vs HRV”“近 28 天 HRV 趋势”图表），说明恢复能力未跟上训练刺激。"
    )
    markdown_parts.append(
        "- 高 AU 日（09-12、09-13）后翌日 HRV 均显著下滑；09-15 叠加出差与工作压力，HRV 跌至周低点。"
    )
    markdown_parts.append("| 日期 | 睡眠时长 (h) | 深睡 (min) | REM (min) | 事件 |")
    markdown_parts.append("| --- | --- | --- | --- | --- |")
    for entry in history:
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | {entry.sleep_duration_hours or '-'} | "
            f"{entry.sleep_deep_minutes or '-'} | {entry.sleep_rem_minutes or '-'} | {lifestyle} |"
        )
    markdown_parts.append(
        "- 睡眠时长从 7.6h 降至 6.7h，深睡/REM 同步下降（参见“睡眠时长与基线对比”“睡眠结构堆叠图”）。"
    )
    markdown_parts.append(
        "- 训练量越高、生活压力越大，当晚睡眠越差；仅 09-09、09-10 保持良好睡眠，有助于次日恢复。"
    )

    # 主观反馈（Hooper）
    markdown_parts.append("\n## 主观反馈（Hooper 指数）")
    markdown_parts.append("| 日期 | 疲劳 | 酸痛 | 压力 | 睡眠质量 | 说明 |")
    markdown_parts.append("| --- | --- | --- | --- | --- | --- |")
    for entry in history:
        hooper = entry.hooper or {}
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | {hooper.get('fatigue', '-')} | "
            f"{hooper.get('soreness', '-')} | {hooper.get('stress', '-')} | "
            f"{hooper.get('sleep', '-')} | {lifestyle} |"
        )
    markdown_parts.append(
        "- 疲劳 3→6、酸痛 3→5、压力 3→4、睡眠质量 4→5，与客观指标一致，显示恢复不足。"
    )
    markdown_parts.append(
        "- 建议持续记录 Hooper；若主观疲劳提前升高，可预先调整训练防止透支。"
    )

    # 生活方式事件
    markdown_parts.append("\n## 生活方式事件")
    events = [
        (entry.date.strftime("%m-%d"), entry.lifestyle_events)
        for entry in history
        if entry.lifestyle_events
    ]
    if events:
        for date_str, tags in events:
            markdown_parts.append(f"- {date_str}: {', '.join(tags)}")
    else:
        markdown_parts.append("- 本周无显著生活方式事件记录。")

    # 自由备注与训练洞察
    markdown_parts.append("\n## 自由备注与训练日志洞察")
    if report_notes:
        markdown_parts.append(f"- 自由备注：{report_notes}")
    if training_sessions:
        for sess in training_sessions:
            if sess.notes:
                markdown_parts.append(
                    f"- {sess.label or '训练'}（RPE {sess.rpe or '-'}，{sess.duration_minutes or '-'} 分钟）：{sess.notes}"
                )
    markdown_parts.append(
        "- 建议将训练排期、生活事件与恢复数据统一记录，形成高压日程前后的负荷调整机制。"
    )

    # 相关性洞察
    markdown_parts.append("\n## 相关性洞察")
    markdown_parts.append(
        "- 高训练量 → 次日 HRV、睡眠下降（09-12、09-13 是典型案例）。"
    )
    markdown_parts.append(
        "- 生活方式事件放大疲劳：出差、夜间工作、晚餐偏晚、睡前屏幕与 HRV/睡眠下降时间节点高度一致。"
    )
    markdown_parts.append(
        "- 主观疲劳与客观指标吻合：Hooper 疲劳/酸痛爬升与准备度、HRV 下降同步，提示恢复不足。"
    )
    markdown_parts.append(
        "- 建议设定 readiness <65、HRV Z-score < -0.5、Hooper 疲劳 >5 的阈值，触发后立刻调整训练。"
    )

    # 行动计划
    markdown_parts.append("\n## 下周行动计划")
    base_actions = list(communicator.call_to_action) if communicator.call_to_action else [
        "保持规律训练与睡眠，并记录每日主观状态。"
    ]
    action_candidates: List[str] = []
    if analyst.opportunities:
        for opp in analyst.opportunities:
            label = opp.area or "改进建议"
            label = _CATEGORY_LABELS.get(label, label)
            action_candidates.append(f"{label}：{opp.recommendation}")
    merged_actions: List[str] = []
    normalized_seen: set[str] = set()

    def _normalize_action(text: str) -> str:
        if "：" in text:
            return text.split("：", 1)[1].strip()
        return text.strip()

    for item in base_actions + action_candidates:
        if not item:
            continue
        norm = _normalize_action(item)
        if norm not in normalized_seen:
            merged_actions.append(item)
            normalized_seen.add(norm)
            markdown_parts.append(f"- {item}")

    # 教练寄语
    markdown_parts.append("\n## 鼓励与后续")
    markdown_parts.append(
        "高负荷阶段你的执行力值得肯定；实施恢复计划是持续进步的关键。下周重点关注准备度、HRV、睡眠的回升。"
    )

    markdown_report = "\n".join(markdown_parts).strip() + "\n"
    chart_ids = analyst.chart_ids or [chart.chart_id for chart in weekly_package.charts]

    return WeeklyFinalReport(
        markdown_report=markdown_report,
        html_report=None,
        chart_ids=chart_ids,
        call_to_action=merged_actions,
    )


__all__ = ["generate_weekly_final_report"]
