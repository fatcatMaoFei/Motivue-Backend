from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weekly_report.finalizer import generate_weekly_final_report
from weekly_report.models import WeeklyFinalReport, WeeklyHistoryEntry
from weekly_report.pipeline import generate_weekly_report
from weekly_report.state import ReadinessState


def _load_state() -> ReadinessState:
    sample_path = Path(__file__).parent / "readiness_state_report_sample.json"
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    state = ReadinessState.model_validate(data)
    if not state.raw_inputs.report_notes:
        state.raw_inputs.report_notes = "本周有一次出差和夜间加班，主观疲劳偏高。"
    # 保证流程从空洞察开始，所有洞察由当前规则/LLM 重新生成
    state.insights = []
    state.insight_reviews = []
    return state


def _build_history(base_date: datetime) -> List[WeeklyHistoryEntry]:
    start = base_date - timedelta(days=6)
    readiness_scores = [72, 70, 68, 66, 65, 64, 64]
    readiness_bands = [
        "Well-adapted",
        "Well-adapted",
        "FOR",
        "FOR",
        "Acute Fatigue",
        "Acute Fatigue",
        "Acute Fatigue",
    ]
    hrv_values = [64, 63, 62, 61, 60, 58, 57]
    hrv_z = [0.2, 0.1, -0.1, -0.3, -0.4, -0.6, -0.85]
    sleep_hours = [7.6, 7.4, 7.2, 7.1, 7.0, 6.8, 6.7]
    deep_minutes = [110, 105, 100, 98, 95, 90, 88]
    rem_minutes = [95, 92, 90, 88, 84, 80, 78]
    au = [320, 360, 420, 500, 560, 520, 510]
    acwr_values = [0.95, 1.02, 1.08, 1.15, 1.32, 1.40, 1.45]
    hooper_fatigue = [3, 3, 4, 5, 6, 6, 6]
    lifestyle = [
        [],
        [],
        [],
        ["late_meal"],
        ["travel"],
        ["late_meal", "screen_before_bed"],
        ["travel", "work_stress"],
    ]

    history: List[WeeklyHistoryEntry] = []
    for idx in range(7):
        day = start + timedelta(days=idx)
        history.append(
            WeeklyHistoryEntry(
                date=day.date(),
                readiness_score=readiness_scores[idx],
                readiness_band=readiness_bands[idx],
                hrv_rmssd=hrv_values[idx],
                hrv_z_score=hrv_z[idx],
                sleep_duration_hours=sleep_hours[idx],
                sleep_total_minutes=int(sleep_hours[idx] * 60),
                sleep_deep_minutes=deep_minutes[idx],
                sleep_rem_minutes=rem_minutes[idx],
                daily_au=au[idx],
                acwr=acwr_values[idx] if idx >= 4 else None,
                hooper={
                    "fatigue": hooper_fatigue[idx],
                    "soreness": 3 + (idx // 3),
                    "stress": 3 + (idx // 4),
                    "sleep": max(7 - idx // 3, 3),
                },
                lifestyle_events=lifestyle[idx],
            )
        )
    return history


def _compare_reports(template: WeeklyFinalReport, generated: WeeklyFinalReport) -> None:
    """粗略对比模板与生成结果的结构，不做失败判定，只输出提示。"""

    import difflib

    template_lines = template.markdown_report.strip().splitlines()
    generated_lines = generated.markdown_report.strip().splitlines()
    diff = list(
        difflib.unified_diff(
            template_lines,
            generated_lines,
            fromfile="template",
            tofile="generated",
            lineterm="",
        )
    )
    if diff:
        print("=== Diff between template and generated markdown (first 200 lines) ===")
        for line in diff[:200]:
            print(line)
        if len(diff) > 200:
            print("... (diff truncated)")
    else:
        print("Generated markdown matches template exactly.")


def main() -> None:
    state = _load_state()
    base_date = datetime.strptime(state.raw_inputs.date or "2025-09-15", "%Y-%m-%d")
    history = _build_history(base_date)
    report = generate_weekly_report(
        state,
        history,
        sleep_baseline_hours=state.metrics.baselines.sleep_baseline_hours,
        hrv_baseline=state.metrics.baselines.hrv_mu,
    )

    final_report = generate_weekly_final_report(
        state,
        report,
        history,
        report_notes=state.raw_inputs.report_notes,
        training_sessions=state.raw_inputs.training_sessions,
    )

    output_path = Path(__file__).parent / "weekly_report_sample.json"
    output_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    final_json_path = Path(__file__).parent / "weekly_report_final_sample.json"
    final_json_path.write_text(
        json.dumps(final_report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    final_md_path = Path(__file__).parent / "weekly_report_final_sample.md"
    final_md_path.write_text(final_report.markdown_report, encoding="utf-8")

    critique_status = (
        "with issues"
        if report.critique and report.critique.issues
        else "no critique issues"
    )
    print(f"Generated weekly report sample -> {output_path} ({critique_status}).")
    print(f"Generated final weekly report JSON -> {final_json_path}")
    print(f"Generated final weekly report Markdown -> {final_md_path}")

    template_path = Path(__file__).parent / "weekly_report_final_template.md"
    if template_path.exists():
        template_report = WeeklyFinalReport(
            markdown_report=template_path.read_text(encoding="utf-8"),
            html_report=None,
            chart_ids=report.analyst.chart_ids,
            call_to_action=final_report.call_to_action,
        )
        _compare_reports(template_report, final_report)
    else:
        print("Template markdown not found; skipping diff.")


if __name__ == "__main__":
    main()
