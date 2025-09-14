from __future__ import annotations

from baseline_analytics import compare_today_vs_baseline, compare_recent_vs_previous


def main() -> None:
    payload = {
        'sleep_duration_hours': [7.2, 6.9, 7.1, 7.4, 6.8, 7.0, 7.3, 6.7],  # last is today
        'sleep_efficiency': [0.82, 0.85, 0.86, 0.84, 0.88, 0.83, 0.86, 0.87],
        'restorative_ratio': [0.33, 0.34, 0.31, 0.36, 0.35, 0.38, 0.33, 0.37],
        'hrv_rmssd': [40, 42, 41, 39, 43, 45, 44, 46],
        'training_au': [300, 280, 400, 0, 350, 200, 500, 100],
    }

    today_vs = compare_today_vs_baseline(
        payload,
        windows=[7, 28],
        baseline_overrides={'hrv_rmssd': 43.0, 'sleep_eff': 0.85, 'rest_ratio': 0.33},
    )
    print('Today vs baseline:', today_vs)

    review = compare_recent_vs_previous(
        payload,
        windows=[7, 28],
        compare_window_map={7: 28},
        baseline_overrides={'hrv_rmssd': 43.0},
    )
    print('Recent vs previous:', review)


if __name__ == '__main__':
    main()

