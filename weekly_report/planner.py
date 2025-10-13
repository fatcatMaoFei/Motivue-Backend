from __future__ import annotations

from datetime import timedelta
from typing import List, Sequence

from weekly_report.models import WeeklyHistoryEntry
from weekly_report.planner_models import DayPlan, MonitorThresholds, NextWeekPlan
from weekly_report.state import ReadinessState


def _recent_load_flags(state: ReadinessState) -> dict:
    tl = state.metrics.training_load
    au7 = tl.daily_au_7d or []
    avg3 = sum(au7[-3:]) / max(len(au7[-3:]), 1) if au7 else 0.0
    au_high = state.metrics.baselines.personalized_thresholds.get("au_high", 500.0)
    low_flag = sum(1 for v in au7 if v is not None and v <= 150) >= 5
    high_flag = avg3 >= au_high
    return {"recent_high": high_flag, "recent_low": low_flag, "avg3": avg3}


def _default_thresholds() -> MonitorThresholds:
    return MonitorThresholds(readiness_lt=65.0, hrv_z_lt=-0.5, hooper_fatigue_gt=5)


def _analyze_type_coverage(history: Sequence[WeeklyHistoryEntry]) -> dict:
    """Infer last-week training type coverage from lifestyle_events tags.

    Supported tags (examples):
      - strength:* (legs/chest/back/upper/lower)
      - push/pull/hinge/squat (free-form)
      - sport:* (tennis/basketball/run/etc.)
    """
    counts = {
        "strength": {},
        "movement": {"push": 0, "pull": 0, "hinge": 0, "squat": 0},
        "sport": {},
    }
    for e in history:
        for tag in (e.lifestyle_events or []):
            if not isinstance(tag, str):
                continue
            t = tag.strip().lower()
            if t.startswith("strength:"):
                key = t.split(":", 1)[1] or "unspecified"
                counts["strength"][key] = counts["strength"].get(key, 0) + 1
            elif t.startswith("sport:"):
                key = t.split(":", 1)[1] or "unspecified"
                counts["sport"][key] = counts["sport"].get(key, 0) + 1
            elif t in counts["movement"]:
                counts["movement"][t] += 1
    return counts


def _build_focus_recommendations(coverage: dict) -> list[str]:
    recs: list[str] = []
    # Identify over/under-represented movement patterns
    mv = coverage.get("movement", {})
    if mv:
        # Simple heuristic: suggest balancing push/pull & hinge/squat
        if mv.get("push", 0) > mv.get("pull", 0) + 1:
            recs.append("补齐拉力训练：加入上肢拉/水平拉动作")
        if mv.get("pull", 0) > mv.get("push", 0) + 1:
            recs.append("补齐推力训练：加入上肢推/水平推动作")
        if mv.get("hinge", 0) > mv.get("squat", 0) + 1:
            recs.append("补齐深蹲模式：安排蹲类模式（前蹲/后蹲/分腿蹲）")
        if mv.get("squat", 0) > mv.get("hinge", 0) + 1:
            recs.append("补齐髋主导：安排硬拉/髋铰链模式（轻中强度）")
    st = coverage.get("strength", {})
    if st:
        # If legs seen >> upper, suggest upper; if chest >> back, suggest back, etc.
        legs = st.get("legs", 0) + st.get("lower", 0)
        upper = st.get("upper", 0) + st.get("chest", 0) + st.get("back", 0)
        if legs > upper + 1:
            recs.append("上肢力量维持：加入上肢推/拉与肩部稳定性训练")
        if upper > legs + 1:
            recs.append("下肢均衡：加入下肢髋/膝主导维持与灵活性")
    # Limit to top-2 suggestions to keep plan concise
    return recs[:2]


def _make_dayplans(
    start_date, template: List[tuple]
) -> List[DayPlan]:
    plans: List[DayPlan] = []
    for i, (load, stype, drills, recovery, rationale) in enumerate(template):
        d = start_date + timedelta(days=i)
        plans.append(
            DayPlan(
                date=d,
                day_label=d.strftime("%m-%d"),
                load_target=load,
                session_type=stype,
                key_drills=list(drills) if drills else [],
                recovery_tasks=list(recovery) if recovery else [],
                rationale=rationale,
                adjustments={
                    "if_trigger": "readiness<65 or hrv_z<-0.5 or hooper_fatigue>5",
                    "action": "降一档强度或将当日改为主动恢复"
                },
            )
        )
    return plans


def build_next_week_plan(
    state: ReadinessState, history: Sequence[WeeklyHistoryEntry]
) -> NextWeekPlan:
    history_sorted = sorted(history, key=lambda x: x.date)
    last_date = history_sorted[-1].date if history_sorted else None
    tl = state.metrics.training_load
    acwr_band = tl.acwr_band
    consecutive_high = tl.consecutive_high_days or 0
    phys = state.metrics.physiology
    hrv_z = phys.hrv_z_score
    rec = state.metrics.recovery
    sleep_delta = rec.sleep_duration_delta
    flags = _recent_load_flags(state)

    # 主客观信号（用于微调：不把建议说死、给出“建议维持或减载”等语气）
    hooper = state.metrics.subjective.hooper_bands or {}
    subj_high = (hooper.get("fatigue") == "high") or (hooper.get("stress") == "high") or \
                ((state.metrics.subjective.fatigue_score or 0) >= 7.0)

    # 目标与模板选择（四象限：剪载 / 维持 / 回升 / 冲击(建议)）
    if acwr_band == "high" or consecutive_high >= 3 or (
        (hrv_z is not None and hrv_z <= -0.5) and (sleep_delta is not None and sleep_delta <= -0.5)
    ):
        # 高 ACWR 或恢复不足：默认剪载；若主观良好，则以“建议维持或减载”表达，不下死结论
        week_objective = "维持或减载（建议）" if not subj_high else "减量与恢复窗口"
        template = [
            ("low", "recovery", ["低强度有氧"], ["睡前无屏幕60min"], "高负荷/恢复不足"),
            ("moderate", "technique", ["技术巩固"], ["拉伸+呼吸训练"], "维持技能"),
            ("low", "recovery", ["步行/拉伸"], ["早睡+营养补给"], "建立恢复窗口"),
            ("moderate", "capacity", ["中强度容量"], ["放松练习"], "逐步回升"),
            ("moderate", "strength", ["基础力量"], ["冷热交替"], "维持训练感"),
            ("low", "recovery", ["灵活性"], ["无屏幕60min"], "巩固恢复"),
            ("moderate", "technique", ["技术/速度"], ["补水营养"], "准备下周"),
        ]
    elif acwr_band == "low" or flags["recent_low"]:
        # ACWR 过低并非理想：提示逐步提高容量，避免去适应；明确建议“回升”而非强冲
        week_objective = "容量回升（建议逐步增加训练量）"
        template = [
            ("moderate", "technique", ["技术激活"], ["拉伸"], "激活准备"),
            ("high", "capacity", ["容量刺激"], ["营养补给"], "回升容量"),
            ("low", "recovery", ["主动恢复"], ["睡眠卫生"], "恢复窗口"),
            ("moderate", "strength", ["力量基础"], ["放松"], "维持适应"),
            ("high", "capacity", ["容量刺激"], ["补水"], "二次提升"),
            ("low", "recovery", ["灵活性"], ["早睡"], "巩固恢复"),
            ("moderate", "technique", ["技术整合"], ["营养"], "准备下周"),
        ]
    else:
        # 安全窗内且恢复/主观良好 → “冲击（建议）”；否则维持
        if (state.metrics.training_load.acwr_value or 0) >= 0.8 and \
           (state.metrics.training_load.acwr_value or 0) <= 1.1 and \
           (hrv_z is None or hrv_z > -0.3) and (sleep_delta is None or sleep_delta > -0.3) and not subj_high:
            week_objective = "冲击周（建议）"
            template = [
                ("high", "capacity", ["专项强度/速度"], ["营养/补水"], "峰值刺激"),
                ("low", "recovery", ["主动恢复"], ["睡眠卫生"], "恢复窗口"),
                ("moderate", "strength", ["力量维持"], ["拉伸"], "稳态巩固"),
                ("low", "recovery", ["灵活性"], ["放松"], "减压"),
                ("moderate", "technique", ["技术整合"], ["补水"], "提升质量"),
                ("low", "recovery", ["呼吸/放松"], ["无屏幕60min"], "巩固恢复"),
                ("moderate", "capacity", ["中等容量"], ["补水"], "准备下周"),
            ]
        else:
            week_objective = "维持与技术巩固"
            template = [
                ("moderate", "technique", ["技术"], ["拉伸"], "巩固技能"),
                ("moderate", "capacity", ["中等容量"], ["补水"], "维持水平"),
                ("low", "recovery", ["主动恢复"], ["睡眠卫生"], "恢复窗口"),
                ("moderate", "strength", ["力量基础"], ["放松"], "维持适应"),
                ("moderate", "capacity", ["中等容量"], ["营养"], "稳态训练"),
                ("low", "recovery", ["灵活性"], ["无屏幕60min"], "巩固恢复"),
                ("moderate", "technique", ["技术/速度"], ["补水"], "准备下周"),
            ]

    start_date = (last_date + timedelta(days=1)) if last_date else None
    day_plans = _make_dayplans(start_date, template) if start_date else []

    # 类型覆盖建议：基于上周标签（strength:/sport:/push/pull/hinge/squat）
    coverage = _analyze_type_coverage(history_sorted)
    focus_recs = _build_focus_recommendations(coverage)

    # 训练频次建议：依据上一周有负荷的天数（AU>au_low）。不强制，仅做模板分配。
    au_low = state.metrics.baselines.personalized_thresholds.get("au_low", 150.0)
    train_days_last_week = sum(1 for e in history_sorted if (e.daily_au or 0) > au_low)
    # 建议频次 3–5：不足 3 → 3；超过 5 → 5；否则取原频次
    suggested_freq = min(5, max(3, train_days_last_week or 3))

    # 根据慢性负荷给 AU 目标区间（可选提示，不强制）
    chronic = state.metrics.training_load.chronic_load or 0.0
    def bounds(level: str):
        if chronic <= 0:
            return (None, None)
        if level == "low":
            return (0.2 * chronic, 0.4 * chronic)
        if level == "moderate":
            return (0.6 * chronic, 1.0 * chronic)
        if level == "high":
            return (1.0 * chronic, 1.4 * chronic)
        return (None, None)

    # 将 7 天模板裁剪为建议频次：优先保留恢复日，其余挑选 evenly spaced 的训练日
    full_plans = _make_dayplans(start_date, template) if start_date else []
    if suggested_freq < 7 and full_plans:
        # 选择训练强度非 low 的天作为训练日候选
        train_candidates = [i for i, dp in enumerate(full_plans) if dp.load_target != "low"]
        if len(train_candidates) > suggested_freq:
            step = len(train_candidates) / float(suggested_freq)
            keep_idx = {train_candidates[int(i * step)] for i in range(suggested_freq)}
        else:
            keep_idx = set(train_candidates)
        pruned: List[DayPlan] = []
        for i, dp in enumerate(full_plans):
            if dp.load_target == "low":
                pruned.append(dp)
            elif i in keep_idx:
                pruned.append(dp)
            else:
                # 非保留的训练日降为恢复原则
                pruned.append(
                    DayPlan(
                        date=dp.date,
                        day_label=dp.day_label,
                        load_target="low",
                        session_type="recovery",
                        key_drills=["主动恢复"],
                        recovery_tasks=["睡眠卫生", "轻度拉伸"],
                        rationale="频次控制以平衡急慢性负荷",
                        adjustments=dp.adjustments,
                    )
                )
        day_plans = pruned
    else:
        day_plans = full_plans

    # 注入 AU 区间提示
    for dp in day_plans:
        lo, hi = bounds(dp.load_target)
        dp.au_target_low = lo
        dp.au_target_high = hi

    # 将类型覆盖建议注入到前 1–2 个训练日的 key_drills
    if focus_recs:
        injected = 0
        for dp in day_plans:
            if dp.load_target != "low":
                # Append missing focus into drills if not present
                for r in focus_recs:
                    if all(r not in (dp.key_drills or []) for _ in [0]):
                        dp.key_drills.append(r)
                        injected += 1
                        break
            if injected >= len(focus_recs):
                break

    guidelines = [
        "控制高负荷日数≤2天且间隔≥48小时",
        "若 readiness<65 或 HRV Z<-0.5 或 疲劳>5，当日降一档或改主动恢复",
        "若出现旅行/酒精/夜班等事件，次日训练降一档或改主动恢复（原则性建议）",
        "ACWR 过低也不理想：建议逐步增加训练容量至 0.8–1.0 区间，避免去适应或突增导致风险",
    ]
    if focus_recs:
        guidelines.insert(0, "类型覆盖建议：" + "；".join(focus_recs))

    plan = NextWeekPlan(
        week_objective=week_objective,
        monitor_thresholds=_default_thresholds(),
        day_plans=day_plans,
        guidelines=guidelines,
        confidence=0.7,
    )
    return plan


__all__ = ["build_next_week_plan"]
