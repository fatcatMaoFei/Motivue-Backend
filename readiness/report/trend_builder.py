from __future__ import annotations

from statistics import mean
from typing import List, Optional, Sequence

from readiness.report.models import ChartSpec, WeeklyHistoryEntry


def build_default_chart_specs(
    history: Sequence[WeeklyHistoryEntry],
    *,
    sleep_baseline_hours: Optional[float] = None,
    hrv_baseline: Optional[float] = None,
) -> List[ChartSpec]:
    """根据历史数据构建默认周报图表集合."""

    entries = sorted(history, key=lambda item: item.date)
    charts: List[ChartSpec] = []

    readiness_chart = _build_readiness_chart(entries)
    if readiness_chart:
        charts.append(readiness_chart)

    readiness_hrv_chart = _build_readiness_hrv_combo(entries)
    if readiness_hrv_chart:
        charts.append(readiness_hrv_chart)

    hrv_chart = _build_hrv_chart(entries, hrv_baseline)
    if hrv_chart:
        charts.append(hrv_chart)

    sleep_chart = _build_sleep_duration_chart(entries, sleep_baseline_hours)
    if sleep_chart:
        charts.append(sleep_chart)

    structure_chart = _build_sleep_structure_chart(entries)
    if structure_chart:
        charts.append(structure_chart)

    load_chart = _build_training_load_chart(entries)
    if load_chart:
        charts.append(load_chart)

    hooper_chart = _build_hooper_radar_chart(entries)
    if hooper_chart:
        charts.append(hooper_chart)

    lifestyle_chart = _build_lifestyle_timeline(entries)
    if lifestyle_chart:
        charts.append(lifestyle_chart)

    return charts


def _date_labels(entries: Sequence[WeeklyHistoryEntry]) -> List[str]:
    return [entry.date.strftime("%m-%d") for entry in entries]


def _build_readiness_chart(entries: Sequence[WeeklyHistoryEntry]) -> Optional[ChartSpec]:
    values = [entry.readiness_score for entry in entries]
    if not any(v is not None for v in values):
        return None
    notes = None
    if entries:
        latest = entries[-1]
        if latest.readiness_score is not None:
            status = latest.readiness_band or "unknown"
            notes = (
                f"最新准备度 {latest.readiness_score:.0f}（band: {status}）。"
            )
    dataset = {
        "xAxis": _date_labels(entries),
        "series": [
            {
                "name": "准备度得分",
                "type": "line",
                "smooth": True,
                "data": values,
            }
        ],
        "normal_range": [70, 100],
    }
    return ChartSpec(
        chart_id="readiness_trend",
        title="近 7 天准备度趋势",
        chart_type="line",
        data=dataset,
        notes=notes,
    )


def _build_readiness_hrv_combo(
    entries: Sequence[WeeklyHistoryEntry],
) -> Optional[ChartSpec]:
    readiness_values = [entry.readiness_score for entry in entries]
    hrv_values = [entry.hrv_rmssd for entry in entries]
    if not (any(v is not None for v in readiness_values) and any(v is not None for v in hrv_values)):
        return None
    dataset = {
        "xAxis": _date_labels(entries),
        "series": [
            {
                "name": "准备度得分",
                "type": "line",
                "yAxisIndex": 0,
                "smooth": True,
                "data": readiness_values,
            },
            {
                "name": "HRV (RMSSD)",
                "type": "line",
                "yAxisIndex": 1,
                "smooth": True,
                "data": hrv_values,
            },
        ],
        "yAxis": [
            {"name": "准备度", "min": 0, "max": 100},
            {"name": "HRV", "min": None, "max": None},
        ],
    }
    return ChartSpec(
        chart_id="readiness_vs_hrv",
        title="准备度 vs HRV",
        chart_type="multi_axis_line",
        data=dataset,
        notes="对照准备度与 HRV 变化，评估恢复是否跟上训练刺激。",
    )


def _build_hrv_chart(
    entries: Sequence[WeeklyHistoryEntry], baseline: Optional[float]
) -> Optional[ChartSpec]:
    values = [entry.hrv_rmssd for entry in entries]
    if not any(v is not None for v in values):
        return None
    baseline_value = baseline
    if baseline_value is None:
        observed = [v for v in values if v is not None]
        baseline_value = mean(observed) if observed else None
    notes = None
    if entries:
        latest = entries[-1]
        if latest.hrv_rmssd is not None and latest.hrv_z_score is not None:
            direction = (
                "下降" if latest.hrv_z_score <= -0.5 else "回升"
                if latest.hrv_z_score >= 0.5
                else "稳定"
            )
            notes = f"最新 HRV {latest.hrv_rmssd:.0f} ms，Z-score {latest.hrv_z_score:+.2f}，趋势判断：{direction}。"
    dataset = {
        "xAxis": _date_labels(entries),
        "series": [
            {
                "name": "HRV (RMSSD)",
                "type": "line",
                "smooth": True,
                "data": values,
            }
        ],
    }
    if baseline_value is not None:
        dataset["baseline"] = baseline_value
    return ChartSpec(
        chart_id="hrv_trend",
        title="近 28 天 HRV 趋势",
        chart_type="line",
        data=dataset,
        notes=notes,
    )


def _build_sleep_duration_chart(
    entries: Sequence[WeeklyHistoryEntry], baseline_hours: Optional[float]
) -> Optional[ChartSpec]:
    values = [entry.sleep_duration_hours for entry in entries]
    if not any(v is not None for v in values):
        return None
    dataset = {
        "xAxis": _date_labels(entries),
        "series": [
            {
                "name": "睡眠时长 (h)",
                "type": "line",
                "smooth": True,
                "data": values,
            }
        ],
    }
    if baseline_hours is not None:
        dataset["baseline"] = baseline_hours
    notes = None
    if entries and entries[-1].sleep_duration_hours is not None and baseline_hours is not None:
        delta = entries[-1].sleep_duration_hours - baseline_hours
        notes = f"最近一日睡眠 {entries[-1].sleep_duration_hours:.1f} 小时，相较基线 {delta:+.1f} 小时。"
    return ChartSpec(
        chart_id="sleep_duration",
        title="睡眠时长与基线对比",
        chart_type="line",
        data=dataset,
        notes=notes,
    )


def _build_sleep_structure_chart(
    entries: Sequence[WeeklyHistoryEntry],
) -> Optional[ChartSpec]:
    if not any(
        entry.sleep_deep_minutes is not None or entry.sleep_rem_minutes is not None
        for entry in entries
    ):
        return None
    categories = _date_labels(entries)
    deep_series = []
    rem_series = []
    light_series = []
    for entry in entries:
        total = entry.sleep_total_minutes or (
            (entry.sleep_duration_hours or 0.0) * 60.0
        )
        deep = entry.sleep_deep_minutes or 0.0
        rem = entry.sleep_rem_minutes or 0.0
        light = max(total - deep - rem, 0.0)
        deep_series.append(round(deep / 60.0, 2))
        rem_series.append(round(rem / 60.0, 2))
        light_series.append(round(light / 60.0, 2))
    dataset = {
        "xAxis": categories,
        "series": [
            {"name": "深睡 (h)", "type": "bar", "stack": "sleep", "data": deep_series},
            {"name": "REM (h)", "type": "bar", "stack": "sleep", "data": rem_series},
            {
                "name": "浅睡/其他 (h)",
                "type": "bar",
                "stack": "sleep",
                "data": light_series,
            },
        ],
    }
    return ChartSpec(
        chart_id="sleep_structure",
        title="睡眠结构堆叠图",
        chart_type="stacked_bar",
        data=dataset,
        notes="展示近 7/28 天睡眠阶段占比，用于识别深睡或 REM 缺口。",
    )


def _build_training_load_chart(
    entries: Sequence[WeeklyHistoryEntry],
) -> Optional[ChartSpec]:
    if not any(entry.daily_au is not None for entry in entries):
        return None
    dataset = {
        "xAxis": _date_labels(entries),
        "series": [
            {
                "name": "训练量 (AU)",
                "type": "bar",
                "data": [entry.daily_au for entry in entries],
            }
        ],
    }
    last_acwr = next(
        (entry.acwr for entry in reversed(entries) if entry.acwr is not None), None
    )
    notes = None
    if last_acwr is not None:
        notes = f"最近 ACWR ≈ {last_acwr:.2f}。若 ≥1.3 需警惕疲劳，≤0.6 留意去适应。"
    return ChartSpec(
        chart_id="training_load",
        title="训练负荷与 ACWR",
        chart_type="bar",
        data=dataset,
        notes=notes,
    )


def _build_hooper_radar_chart(
    entries: Sequence[WeeklyHistoryEntry],
) -> Optional[ChartSpec]:
    if not entries:
        return None
    latest = entries[-1]
    hooper = latest.hooper or {}
    axes = ["fatigue", "soreness", "stress", "sleep"]
    values = [hooper.get(axis) for axis in axes]
    if not any(v is not None for v in values):
        return None
    dataset = {
        "indicator": [
            {"name": axis, "max": 10, "min": 0} for axis in ["疲劳", "酸痛", "压力", "睡眠质量"]
        ],
        "series": [
            {
                "name": latest.date.strftime("%m-%d"),
                "type": "radar",
                "data": [
                    [
                        hooper.get("fatigue") or 0,
                        hooper.get("soreness") or 0,
                        hooper.get("stress") or 0,
                        hooper.get("sleep") or 0,
                    ]
                ],
            }
        ],
    }
    return ChartSpec(
        chart_id="hooper_radar",
        title="主观疲劳雷达",
        chart_type="radar",
        data=dataset,
        notes="雷达图展示最新 Hooper 评分，便于识别主观疲劳与压力。",
    )


def _build_lifestyle_timeline(
    entries: Sequence[WeeklyHistoryEntry],
) -> Optional[ChartSpec]:
    annotated = [
        (entry.date.strftime("%m-%d"), list(entry.lifestyle_events))
        for entry in entries
        if entry.lifestyle_events
    ]
    if not annotated:
        return None
    dataset = {
        "events": [
            {"date": date_label, "tags": tags} for date_label, tags in annotated
        ]
    }
    return ChartSpec(
        chart_id="lifestyle_timeline",
        title="生活方式事件概览",
        chart_type="timeline",
        data=dataset,
        notes="标注旅行、加班等事件，便于对照 HRV/睡眠变化。",
    )
