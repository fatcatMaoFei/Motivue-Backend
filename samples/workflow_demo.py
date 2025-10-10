from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from readiness.workflow.graph import run_workflow_json


SAMPLE_PAYLOAD = {
    "user_id": "athlete_001",
    "date": "2025-09-15",
    "gender": "男性",
    "total_sleep_minutes": 420,
    "in_bed_minutes": 470,
    "deep_sleep_minutes": 90,
    "rem_sleep_minutes": 95,
    "apple_sleep_score": 82,
    "hrv_rmssd_today": 58,
    "hrv_rmssd_3day_avg": 55,
    "hrv_rmssd_7day_avg": 60,
    "hrv_rmssd_28day_avg": 62.5,
    "hrv_rmssd_28day_sd": 6.3,
    "hrv_baseline_mu": 63,
    "hrv_baseline_sd": 5.8,
    "sleep_baseline_hours": 7.6,
    "sleep_baseline_eff": 0.87,
    "rest_baseline_ratio": 0.37,
    "recent_training_au": [0, 500, 420, 560, 300, 360, 440],
    "training_sessions": [
        {
            "label": "高",
            "rpe": 8,
            "duration_minutes": 70,
            "au": 560,
            "start_time": "2025-09-14T18:30:00",
        }
    ],
    "hooper": {"fatigue": 6, "soreness": 5, "stress": 3, "sleep": 4},
    "journal": {
        "alcohol_consumed": False,
        "late_caffeine": False,
        "screen_before_bed": True,
        "late_meal": False,
        "lifestyle_tags": ["work_travel"],
        "sliders": {"fatigue_slider": 6, "mood_slider": 3},
    },
}


def main() -> None:
    print(run_workflow_json(SAMPLE_PAYLOAD))


if __name__ == "__main__":
    main()
