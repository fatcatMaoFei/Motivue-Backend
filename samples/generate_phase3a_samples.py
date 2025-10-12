from __future__ import annotations

import json
from pathlib import Path

import sys
from pathlib import Path

# Ensure repository root is on sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weekly_report.workflow.graph import run_workflow, state_to_json


def main() -> None:
    # Sample payload designed to trigger a "complex" case
    payload = {
        "user_id": "athlete_demo",
        "date": "2025-09-15",
        "gender": "male",

        # Raw inputs
        "total_sleep_minutes": 420,   # 7.0h
        "in_bed_minutes": 470,        # ~0.89 efficiency
        "deep_sleep_minutes": 90,
        "rem_sleep_minutes": 95,

        # HRV today and baselines
        "hrv_rmssd_today": 58.0,
        "hrv_baseline_mu": 63.0,
        "hrv_baseline_sd": 5.8,

        # Personalized baselines
        "sleep_baseline_hours": 7.6,
        "sleep_baseline_eff": 0.87,
        "rest_baseline_ratio": 0.37,

        # Personalized thresholds to make ACWR more sensitive
        "personalized_thresholds": {
            "acwr_high": 1.25,
            "acwr_low": 0.6,
            "au_high": 500.0,
            "hrv_decline": -0.5,
        },

        # Recent AU (28 days). Ensure last 7d acute avg >> chronic avg
        # and last 3 days are all high to trigger consecutive-high-days
        "recent_training_au": [
            200, 300, 0,  480, 360, 420, 300,
            260, 0,   340, 380, 0,   420, 300,
            0,   360, 400, 0,   500, 420, 560,
            300, 360, 480, 520, 560, 510,
        ],

        # Today sessions (optional)
        "training_sessions": [
            {"label": "高", "rpe": 8, "duration_minutes": 70, "au": 560, "notes": "力量训练-背部"}
        ],

        # Hooper and journal
        "hooper": {"fatigue": 6, "soreness": 5, "stress": 3, "sleep": 4},
        "journal": {
            "alcohol_consumed": False,
            "late_caffeine": False,
            "screen_before_bed": True,
            "late_meal": False,
            "lifestyle_tags": ["work_travel"],
            "sliders": {"fatigue_slider": 6.0, "mood_slider": 3.0},
        },
        "bodyweight_kg": 83.4,
        "resting_hr": 52.0,
        "report_notes": "昨晚赶飞机回程，入睡前加班处理工作，整体感觉疲劳较高。",
    }

    out_dir = Path(__file__).parent

    # Save input payload for reference
    (out_dir / "phase3a_input_sample.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Run workflow to get intermediate metadata and final state
    gs = run_workflow(payload, auto_insights=True)

    # Extract intermediate artifacts from GraphState.metadata
    complexity = gs.metadata.get("complexity")
    tot_hypotheses = gs.metadata.get("tot_hypotheses")
    critique = gs.metadata.get("critique")

    if complexity is not None:
        (out_dir / "phase3a_complexity.json").write_text(
            json.dumps(complexity, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if tot_hypotheses is not None:
        (out_dir / "phase3a_tot_hypotheses.json").write_text(
            json.dumps(tot_hypotheses, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if critique is not None:
        (out_dir / "phase3a_critique.json").write_text(
            json.dumps(critique, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Insight review record appended to state
    insight_reviews = gs.state.insight_reviews
    (out_dir / "phase3a_insight_reviews.json").write_text(
        json.dumps(insight_reviews, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Final readiness_state JSON
    (out_dir / "phase3a_final_readiness_state.json").write_text(
        state_to_json(gs.state, indent=2), encoding="utf-8"
    )

    print("Generated Phase 3A samples:")
    for name in [
        "phase3a_input_sample.json",
        "phase3a_complexity.json",
        "phase3a_tot_hypotheses.json",
        "phase3a_critique.json",
        "phase3a_insight_reviews.json",
        "phase3a_final_readiness_state.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
