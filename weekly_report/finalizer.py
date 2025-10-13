from __future__ import annotations

import logging
from datetime import date
from typing import Iterable, List, Optional, Sequence

from weekly_report.llm.provider import LLMCallError, LLMProvider, get_llm_provider
from weekly_report.models import (
    CommunicatorReport,
    CommunicatorSection,
    WeeklyFinalReport,
    WeeklyHistoryEntry,
    WeeklyReportPackage,
)
from weekly_report.state import ReadinessState, TrainingSessionInput

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
    use_llm: bool = True,
) -> WeeklyFinalReport:
    """Phase 5：生成最终 Markdown/HTML 周报。"""

    communicator = _apply_critique_fixes(
        weekly_package.communicator, weekly_package.critique
    )
    package = weekly_package.model_copy(update={"communicator": communicator})
    llm: Optional[LLMProvider] = provider
    if llm is None and use_llm:
        llm = get_llm_provider()

    if llm is not None:
        try:
            return llm.generate_weekly_final_report(
                weekly_package=package,
                history=history,
                report_notes=report_notes,
                training_sessions=list(training_sessions or state.raw_inputs.training_sessions),
                next_week_plan=(
                    state.next_week_plan.model_dump(mode="json") if state.next_week_plan else None
                ),
            )
        except LLMCallError as exc:
            logger.warning("Weekly finalizer LLM failed, fallback to heuristic: %s", exc)

    return _fallback_final_report(
        weekly_package=package,
        history=history,
        communicator=communicator,
        report_notes=report_notes,
        training_sessions=list(training_sessions or state.raw_inputs.training_sessions),
        state=state,
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
    state: ReadinessState,
) -> WeeklyFinalReport:
    analyst = weekly_package.analyst
    history_sorted = sorted(history, key=lambda item: item.date)

    def _fmt_readiness(entry: WeeklyHistoryEntry) -> str:
        if entry.readiness_score is None:
            return "-"
        band = entry.readiness_band or "未知"
        return f"{entry.readiness_score:.0f} / {band}"

    def _avg(values: Sequence[Optional[float]]) -> Optional[float]:
        nums = [float(v) for v in values if v is not None]
        if not nums:
            return None
        return sum(nums) / len(nums)

    def _fmt_number(value: Optional[float], digits: int = 1) -> str:
        if value is None:
            return "-"
        return f"{value:.{digits}f}"

    def _latest(values: Sequence[Optional[float]]) -> Optional[float]:
        for item in reversed(values):
            if item is not None:
                return float(item)
        return None

    latest_entry = history_sorted[-1] if history_sorted else None
    headline_date = (
        latest_entry.date if latest_entry else (state.raw_inputs.date or date.today())
    )
    if isinstance(headline_date, str):
        headline_str = headline_date
    else:
        headline_str = headline_date.strftime("%Y-%m-%d")

    readiness_values = [entry.readiness_score for entry in history_sorted]
    readiness_numeric = [float(v) for v in readiness_values if v is not None]
    au_values = [float(entry.daily_au) for entry in history_sorted if entry.daily_au is not None]
    sleep_hours = [entry.sleep_duration_hours for entry in history_sorted]
    sleep_numeric = [float(v) for v in sleep_hours if v is not None]
    hrv_values = [entry.hrv_rmssd for entry in history_sorted]
    hrv_numeric = [float(v) for v in hrv_values if v is not None]
    hrv_z_values = [entry.hrv_z_score for entry in history_sorted]

    acwr_latest = next(
        (entry.acwr for entry in reversed(history_sorted) if entry.acwr is not None),
        None,
    )
    readiness_avg = _avg(readiness_numeric)
    readiness_min = min(readiness_numeric) if readiness_numeric else None
    readiness_max = max(readiness_numeric) if readiness_numeric else None
    readiness_latest = _latest(readiness_values)
    latest_band = latest_entry.readiness_band if latest_entry else None
    latest_readiness_text = "-" if readiness_latest is None else f"{readiness_latest:.0f}"

    au_min = min(au_values) if au_values else None
    au_max = max(au_values) if au_values else None

    summary_lines: List[str] = []
    if history_sorted:
        if au_values:
            summary_lines.append(
                f"- 本周记录 {len(history_sorted)} 天，日训练量范围 {au_min:.0f}–{au_max:.0f} AU。"
                if au_min is not None and au_max is not None and au_min != au_max
                else f"- 本周记录 {len(history_sorted)} 天，训练量约 {au_min:.0f} AU。"
            )
        else:
            summary_lines.append(
                f"- 本周记录 {len(history_sorted)} 天，但缺少训练量 AU 数据。"
            )
        if readiness_numeric:
            summary_lines.append(
                f"- 周均准备度 {readiness_avg:.0f} 分（范围 {readiness_min:.0f}→{readiness_max:.0f}），"
                f"最新 {latest_readiness_text} 分，分档 {latest_band or '未知'}。"
            )
        else:
            summary_lines.append("- 准备度数据不足，建议补充每日 readiness 记录。")
    else:
        summary_lines.append("- 本周缺少历史数据，建议重新生成周报并检查输入。")
    if acwr_latest is not None:
        if acwr_latest >= 1.3:
            summary_lines.append(
                f"- ACWR {acwr_latest:.2f} ≥ 1.30，高负荷风险需安排恢复日。"
            )
        elif acwr_latest <= 0.6:
            summary_lines.append(
                f"- ACWR {acwr_latest:.2f} ≤ 0.60，建议适度增加训练刺激。"
            )
        else:
            summary_lines.append(
                f"- ACWR {acwr_latest:.2f} 处于安全窗口，继续维持渐进式训练。"
            )
    if analyst.summary_points:
        seen_points: set[str] = set()
        for point in analyst.summary_points:
            point_clean = point.strip()
            if not point_clean or point_clean in seen_points:
                continue
            summary_lines.append(f"- {point_clean}")
            seen_points.add(point_clean)
            if len(seen_points) >= 2:
                break
    if len(summary_lines) < 4:
        summary_lines.append("- 维持规律睡眠与营养，确保恢复与监测同步进行。")

    markdown_parts: List[str] = []
    markdown_parts.append(f"# 周报总览（{headline_str}）")

    markdown_parts.append("## 本周概览")
    markdown_parts.extend(summary_lines)

    markdown_parts.append("\n## 训练负荷与表现")
    # 图表占位工具与可用集（仅为存在的图表注入锚点）
    try:
        _available_chart_ids = {c.chart_id for c in weekly_package.charts}
    except Exception:
        _available_chart_ids = set()
    def _anchor(cid: str) -> str:
        return f"[[chart:{cid}]]" if cid in _available_chart_ids else ""
    markdown_parts.append("| 日期 | 训练量 (AU) | 准备度分数 / 分档 | 生活方式事件 / 备注 |")
    markdown_parts.append("| --- | --- | --- | --- |")
    for entry in history_sorted:
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "-"
        au_text = f"{entry.daily_au:.0f}" if entry.daily_au is not None else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | {au_text} | {_fmt_readiness(entry)} | {lifestyle} |"
        )

    # 锚点：训练负荷与整体趋势
    anchor_training = _anchor("training_load")
    if anchor_training:
        markdown_parts.append(anchor_training)
    anchor_readiness = _anchor("readiness_trend")
    if anchor_readiness:
        markdown_parts.append(anchor_readiness)

    markdown_parts.append("- 每日重点")
    for entry in history_sorted:
        daily_items = []
        if entry.daily_au is not None:
            daily_items.append(f"AU {entry.daily_au:.0f}")
        daily_items.append(f"准备度 {_fmt_readiness(entry)}")
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "无"
        daily_items.append(f"事件：{lifestyle}")
        markdown_parts.append(f"  - {entry.date:%m-%d}: " + "，".join(daily_items))

    load_notes: List[str] = []
    if acwr_latest is not None:
        if acwr_latest >= 1.3:
            load_notes.append(
                "- ACWR 高于警戒线，建议插入恢复性训练并监控疲劳反应。"
            )
        elif acwr_latest <= 0.6:
            load_notes.append("- ACWR 偏低，适度增加训练量以维持适应。")
        else:
            load_notes.append("- ACWR 位于理想区间，维持当前训练节奏。")
    high_days = sum(1 for value in au_values if value >= 500)
    if high_days:
        load_notes.append(f"- 本周有 {high_days} 天 AU ≥500，连续高压日后需安排低负荷。")
    low_days = sum(1 for value in au_values if value <= 150)
    if low_days:
        load_notes.append(f"- 低负荷日（AU ≤150）共 {low_days} 天，可用于主动恢复。")
    if not load_notes:
        load_notes = [
            "- 缺少训练量趋势参考，建议在客户端补全 AU 数据。",
            "- 根据准备度反馈灵活调整下周训练安排。",
        ]
    markdown_parts.extend(load_notes[:2])

    markdown_parts.append("\n## 恢复与生理信号")
    markdown_parts.append("| 日期 | HRV (RMSSD) | Z-score | 训练 / 事件备注 |")
    markdown_parts.append("| --- | --- | --- | --- |")
    for entry in history_sorted:
        z = f"{entry.hrv_z_score:+.2f}" if entry.hrv_z_score is not None else "-"
        events = []
        if entry.daily_au is not None:
            events.append(f"AU {entry.daily_au:.0f}")
        if entry.lifestyle_events:
            events.extend(entry.lifestyle_events)
        hrv_text = f"{entry.hrv_rmssd:.0f}" if entry.hrv_rmssd is not None else "-"
        event_text = ", ".join(events) if events else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | {hrv_text} | {z} | {event_text} |"
        )

    # 锚点：HRV 趋势与 readiness 对照
    anchor_hrv = _anchor("hrv_trend")
    if anchor_hrv:
        markdown_parts.append(anchor_hrv)
    anchor_combo = _anchor("readiness_vs_hrv")
    if anchor_combo:
        markdown_parts.append(anchor_combo)

    hrv_lines: List[str] = []
    if hrv_numeric:
        hrv_first = float(next(v for v in hrv_values if v is not None))
        hrv_last = float(_latest(hrv_values) or hrv_first)
        delta = hrv_last - hrv_first
        hrv_lines.append(
            f"- HRV 均值 { _avg(hrv_numeric):.1f} ms，较周初变化 {delta:+.1f} ms。"
        )
        hrv_z_last = _latest(hrv_z_values)
        if hrv_z_last is not None:
            hrv_lines.append(
                f"- 最新 HRV Z-score {hrv_z_last:+.2f}，结合准备度判断当前恢复水平。"
            )
    else:
        hrv_lines = [
            "- 未提供 HRV 数据，建议继续记录以评估恢复。",
            "- 当缺乏 HRV 监测时，可结合主观疲劳与睡眠质量作参考。",
        ]
    markdown_parts.extend(hrv_lines[:2])

    markdown_parts.append("| 日期 | 睡眠时长 (h) | 深睡 (min) | REM (min) | 事件 |")
    markdown_parts.append("| --- | --- | --- | --- | --- |")
    for entry in history_sorted:
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | "
            f"{_fmt_number(entry.sleep_duration_hours, 1)} | "
            f"{entry.sleep_deep_minutes or '-'} | "
            f"{entry.sleep_rem_minutes or '-'} | {lifestyle} |"
        )

    # 锚点：睡眠时长与结构
    anchor_sleep = _anchor("sleep_duration")
    if anchor_sleep:
        markdown_parts.append(anchor_sleep)
    anchor_struct = _anchor("sleep_structure")
    if anchor_struct:
        markdown_parts.append(anchor_struct)

    sleep_lines: List[str] = []
    if sleep_numeric:
        sleep_avg = _avg(sleep_numeric)
        sleep_last = float(_latest(sleep_hours) or sleep_numeric[0])
        sleep_first = float(next(v for v in sleep_hours if v is not None))
        sleep_lines.append(
            f"- 平均睡眠 {sleep_avg:.1f} 小时，较周初变化 {sleep_last - sleep_first:+.1f} 小时。"
        )
        if state.metrics.baselines.sleep_baseline_hours is not None:
            baseline = state.metrics.baselines.sleep_baseline_hours
            sleep_lines.append(
                f"- 与基线 {baseline:.1f} 小时相比，最新一夜差异 {sleep_last - baseline:+.1f} 小时。"
            )
    else:
        sleep_lines = [
            "- 未提供睡眠数据，建议同步可穿戴设备或手动填报。",
            "- 睡眠缺失时，可通过安排早睡与放松训练提升恢复。"
        ]
    markdown_parts.extend(sleep_lines[:2])

    markdown_parts.append("\n## 主观反馈（Hooper 指数）")
    markdown_parts.append("| 日期 | 疲劳 | 酸痛 | 压力 | 睡眠质量 | 说明 |")
    markdown_parts.append("| --- | --- | --- | --- | --- | --- |")
    hooper_summary: List[str] = []
    fatigue_scores: List[float] = []
    for entry in history_sorted:
        hooper = entry.hooper or {}
        fatigue = hooper.get("fatigue")
        soreness = hooper.get("soreness")
        stress = hooper.get("stress")
        sleep = hooper.get("sleep")
        if fatigue is not None:
            fatigue_scores.append(float(fatigue))
        lifestyle = ", ".join(entry.lifestyle_events) if entry.lifestyle_events else "-"
        markdown_parts.append(
            f"| {entry.date:%m-%d} | "
            f"{fatigue if fatigue is not None else '-'} | "
            f"{soreness if soreness is not None else '-'} | "
            f"{stress if stress is not None else '-'} | "
            f"{sleep if sleep is not None else '-'} | {lifestyle or '-'} |"
        )

    # 锚点：Hooper 雷达
    anchor_hooper = _anchor("hooper_radar")
    if anchor_hooper:
        markdown_parts.append(anchor_hooper)

    if fatigue_scores:
        hooper_summary.append(
            f"- Hooper 疲劳均值 { _avg(fatigue_scores):.1f} 分，请与准备度对照评估过度疲劳。"
        )
    if communicator.call_to_action:
        hooper_summary.append(
            f"- 本周重点关注：{'；'.join(communicator.call_to_action[:2])}"
        )
    while len(hooper_summary) < 2:
        hooper_summary.append("- 建议持续记录 Hooper 四项，发现主客观分歧及时沟通。")
    markdown_parts.extend(hooper_summary[:2])

    markdown_parts.append("\n## 生活方式事件")
    lifestyle_lines: List[str] = []
    for entry in history_sorted:
        if entry.lifestyle_events:
            lifestyle_lines.append(
                f"- {entry.date:%m-%d}: " + "，".join(entry.lifestyle_events)
            )
    if lifestyle_lines:
        markdown_parts.extend(lifestyle_lines)
    else:
        markdown_parts.append("- 本周无显著生活方式事件记录。")

    # 锚点：生活方式时间线
    anchor_life = _anchor("lifestyle_timeline")
    if anchor_life:
        markdown_parts.append(anchor_life)

    markdown_parts.append("\n## 自由备注与训练日志洞察")
    note_lines: List[str] = []
    if report_notes:
        note_lines.append(f"- 教练/运动员备注：{report_notes.strip()}")
    for session in training_sessions:
        description = []
        if session.label:
            description.append(session.label)
        if session.duration_minutes is not None:
            description.append(f"{session.duration_minutes:.0f} 分钟")
        if session.au is not None:
            description.append(f"AU {session.au:.0f}")
        if session.notes:
            description.append(session.notes)
        if description:
            note_lines.append(f"- 训练日志：{'，'.join(description)}")
    if not note_lines:
        note_lines.append("- 本周未记录额外备注与训练日志。")
    markdown_parts.extend(note_lines)

    markdown_parts.append("\n## 相关性洞察")
    correlation_lines: List[str] = []
    if readiness_numeric and sleep_numeric:
        readiness_delta = readiness_numeric[-1] - readiness_numeric[0]
        sleep_delta = (sleep_numeric[-1] - sleep_numeric[0]) if len(sleep_numeric) > 1 else 0.0
        correlation_lines.append(
            f"- 准备度从 {readiness_numeric[0]:.0f} 分变化到 {readiness_numeric[-1]:.0f} 分，同时睡眠时长变化 {sleep_delta:+.1f} 小时。"
        )
    if readiness_numeric and hrv_numeric:
        readiness_delta = readiness_numeric[-1] - readiness_numeric[0]
        hrv_delta = hrv_numeric[-1] - hrv_numeric[0] if len(hrv_numeric) > 1 else 0.0
        correlation_lines.append(
            f"- HRV 变化 {hrv_delta:+.1f} ms 与准备度变化 {readiness_delta:+.0f} 分形成联动，需保持恢复窗口。"
        )
    if acwr_latest is not None and readiness_numeric:
        correlation_lines.append(
            f"- 当前 ACWR {acwr_latest:.2f} 对应准备度 {readiness_numeric[-1]:.0f} 分，注意高 ACWR 时的恢复策略。"
        )
    if not correlation_lines:
        correlation_lines = [
            "- 数据不足以计算具体关联，请完善训练、睡眠与主观反馈。",
            "- 维持黏性的记录习惯可帮助发现训练-恢复因果关系。",
            "- 建议每周复盘 ACWR、HRV 与 Hooper 指数的同步程度。"
        ]
    markdown_parts.extend(correlation_lines[:3])

    markdown_parts.append("\n## 下周行动计划")
    # 若 Planner 已给出 next_week_plan，则优先渲染分日计划；否则回退到机会/行动提醒
    if getattr(state, "next_week_plan", None) and state.next_week_plan and state.next_week_plan.day_plans:
        plan = state.next_week_plan
        markdown_parts.append(f"- 本周目标：{plan.week_objective}")
        mt = plan.monitor_thresholds
        mt_text = []
        if mt.readiness_lt is not None:
            mt_text.append(f"准备度<{mt.readiness_lt:.0f}")
        if mt.hrv_z_lt is not None:
            mt_text.append(f"HRV Z<{mt.hrv_z_lt:+.1f}")
        if mt.hooper_fatigue_gt is not None:
            mt_text.append(f"疲劳>{mt.hooper_fatigue_gt:.0f}")
        if mt_text:
            markdown_parts.append("- 监测阈值：" + "，".join(mt_text) + "（触发则当日降一档/改主动恢复）")
        markdown_parts.append("- 分日安排：")
        for dp in plan.day_plans:
            label = dp.day_label or (dp.date.strftime("%m-%d") if dp.date else "D")
            drills = f"；重点：{'、'.join(dp.key_drills)}" if dp.key_drills else ""
            recs = f"；恢复：{'、'.join(dp.recovery_tasks)}" if dp.recovery_tasks else ""
            rationale = f"；依据：{dp.rationale}" if dp.rationale else ""
            markdown_parts.append(
                f"  - {label}: {dp.load_target} / {dp.session_type}{drills}{recs}{rationale}"
            )
    else:
        action_lines: List[str] = []
        seen_action_lines: set[str] = set()
        opportunity_lines = 0
        for opp in analyst.opportunities:
            label = _CATEGORY_LABELS.get(
                opp.area,
                "洞察修正" if opp.area == "analysis" else (opp.area or "重点行动"),
            )
            reason = f"（依据：{opp.reason}）" if opp.reason else ""
            line = f"- {label}：{opp.recommendation}{reason}"
            if line not in seen_action_lines:
                action_lines.append(line)
                seen_action_lines.add(line)
                opportunity_lines += 1
            if opportunity_lines >= 2:
                break
        for action in communicator.call_to_action:
            line = f"- 行动提醒：{action}"
            if line not in seen_action_lines:
                action_lines.append(line)
                seen_action_lines.add(line)
        defaults = [
            "- 训练负荷管理：安排 1–2 天低负荷或技术训练，检查 ACWR 是否回落到安全区。",
            "- 恢复策略：保持连续 7.5 小时睡眠，并加入主动放松（呼吸、拉伸）。",
            "- 生活方式：减少晚间电子屏幕与咖啡因，优化睡前环境。",
            "- 监测提醒：每天同步 Hooper/HRV，异常时及时与教练沟通。",
        ]
        for default in defaults:
            if len(action_lines) >= 4:
                break
            action_lines.append(default)
        markdown_parts.extend(action_lines[:4])

    markdown_parts.append("\n## 鼓励与后续")
    encouragement: Optional[str] = None
    if communicator.call_to_action:
        primary_action = communicator.call_to_action[0].rstrip("。")
        encouragement = (
            f"辛苦了！优先落实：{primary_action}。"
            "保持训练与恢复平衡，关注准备度与 HRV 的回升。"
        )
    if not encouragement:
        readiness_sentence = (
            f"当前准备度 {latest_readiness_text} 分，"
            if latest_readiness_text != "-"
            else "请保持补全准备度记录，"
        )
        encouragement = (
            f"辛苦了！{readiness_sentence}按计划执行行动项，下周重点关注准备度、HRV 与睡眠的同步改善。"
        )
    markdown_parts.append(encouragement)

    chart_ids = (
        list(weekly_package.analyst.chart_ids)
        if weekly_package.analyst.chart_ids
        else [chart.chart_id for chart in weekly_package.charts[:5]]
    )
    call_to_action = (
        list(communicator.call_to_action)
        if communicator.call_to_action
        else ["保持规律睡眠并跟踪准备度变化。"]
    )

    return WeeklyFinalReport(
        markdown_report="\n".join(markdown_parts),
        html_report=None,
        chart_ids=chart_ids,
        call_to_action=call_to_action,
    )

    # （重复段落已移除）

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
