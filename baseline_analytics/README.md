# Baseline Analytics

Independent of readiness/mapping, this module provides two windowed comparisons:

- Today vs Baseline Window
  - API: compare_today_vs_baseline(payload, windows=[7,28,56], tol_pct=1.0, baseline_overrides=None)
  - Logic: compare today vs mean of past N days (excluding today); optional aseline_overrides to compare today vs global baselines (e.g., HRV µ)
  - Metrics: sleep_hours, sleep_eff, est_ratio, hrv_rmssd, 	raining_au
- Recent N vs Previous N
  - API: compare_recent_vs_previous(payload, windows=[7,28,56], tol_pct=1.0, compare_window_map=None, baseline_overrides=None)
  - Logic: mean of recent N vs previous N; compare_window_map supports custom previous window per N (e.g., {7: 28} for 7 vs previous 28). aseline_overrides compares recent window avg vs a global baseline.
  - Metrics: same as above

## Input format (payload)
- Arrays of daily values; the last element is today (only used by the daily API):
  - sleep_hours or sleep_duration_hours: [hours, ...]
  - sleep_eff or sleep_efficiency: [0..1 or 0..100, ...] (normalized to 0..1)
  - est_ratio or estorative_ratio: [0..1, ...]
  - hrv_rmssd or hrv: [ms, ...]
  - 	raining_au: [AU, ...]
Optional global baselines (overrides):
  - aseline_overrides = { 'sleep_hours': 7.1, 'sleep_eff': 0.86, 'rest_ratio': 0.33, 'hrv_rmssd': 43.0, 'training_au': 230 }

## Output format
- Returns a dict per metric with per-window results under windows; when aseline_overrides is provided, an override entry is also included per metric.
- Daily example:
  `json
  {
    "sleep_hours": {
      "windows": {
        "7": {"today": 6.8, "baseline_avg": 7.1, "pct_change": -4.2, "is_up": false, "is_down": true, "is_flat": false, "direction": "down", "window": 7}
      },
      "override": {"today": 6.8, "baseline": 7.2, "pct_change": -5.6, "is_up": false, "is_down": true, "is_flat": false}
    }
  }
  `
- Periodic example:
  `json
  {
    "hrv_rmssd": {
      "windows": {
        "28": {"last_avg": 45.2, "prev_avg": 42.0, "pct_change": 7.6, "is_up": true, "direction": "up", "window": 28, "compare_window": 28}
      },
      "override": {"last_avg": 45.2, "baseline": 43.0, "pct_change": 5.1, "is_up": true}
    }
  }
  `
- 	ol_pct controls the absolute percent treated as flat (default 1%).

## Usage example
`python
from baseline_analytics import compare_today_vs_baseline, compare_recent_vs_previous

payload = {
  'sleep_duration_hours': [7.2, 6.9, 7.1, 7.4, 6.8, 7.0, 7.3, 6.7],  # last item is today
  'sleep_efficiency': [0.82, 0.85, 0.86, 0.84, 0.88, 0.83, 0.86, 0.87],
  'restorative_ratio': [0.33, 0.34, 0.31, 0.36, 0.35, 0.38, 0.33, 0.37],
  'hrv_rmssd': [40, 42, 41, 39, 43, 45, 44, 46],
  'training_au': [300, 280, 400, 0, 350, 200, 500, 100],
}

today_vs = compare_today_vs_baseline(payload, windows=[7, 28], baseline_overrides={'hrv_rmssd': 43.0})
review = compare_recent_vs_previous(payload, windows=[7, 28], compare_window_map={7: 28})
`

## Design notes
- Decoupled from readiness/mapping; purely window means on arrays.
- Custom windows supported (e.g., 7/28/56/any). Default [7, 28, 56].
- Ratio metrics (efficiency/restorative) accept 0..1 or 0..100; normalized to 0..1.
- Returns direction booleans and direction enum (up/down/flat).

## Notes
- If you already have global baselines from the baseline module (e.g., hrv_baseline_mu), pass them via aseline_overrides when needed. By default, this module uses window means for comparisons.
