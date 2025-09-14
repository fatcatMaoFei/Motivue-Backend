# Physiological Age

A production‑oriented physiological age engine based on an age×gender master
reference (yearly norms µ/σ for SDNN, RHR, CSS). It finds the age whose norms
best match the user’s recent 30‑day baseline (SDNN/RHR) and today’s sleep (CSS).

## Algorithm Overview
- Inputs: 30‑day baseline for SDNN and RHR; today’s sleep raw data to compute CSS.
- For each candidate age (default 20..80):
  - Lookup µ/σ for SDNN/RHR/CSS by (age, gender)
  - z_sdnn = (SDNN − µ_sdnn) / σ_sdnn
  - z_rhr = −(RHR − µ_rhr) / σ_rhr   # reversed so positive is better
  - z_css = (CSS − µ_css) / σ_css
  - cost = 0.45·z_sdnn² + 0.20·z_rhr² + 0.35·z_css²
  - pick minimal cost as physiological_age
- Additionally compute a soft‑min weighted fractional age (physiological_age_weighted).

## Minimal Input (Raw)
- `user_gender`: '男性' | '女性' (also accepts 'male'|'female')
- 30‑day series (most recent last; len ≥ 30):
  - `sdnn_series`: [ms, ...]
  - `rhr_series`:  [bpm, ...]
- Today sleep raw (4 fields):
  - `total_sleep_minutes`
  - `in_bed_minutes` (or `time_in_bed_minutes`)
  - `deep_sleep_minutes`
  - `rem_sleep_minutes`

## CSS (Composite Sleep Score, 0–100)
Computed from today’s raw sleep (no personal baseline):
- Duration hours = total_sleep_minutes / 60
  - <4h→0; 4–7h→linear→100; 7–9h→100; 9–11h→linear→50; >11h→50
- Efficiency = total_sleep_minutes / in_bed_minutes (clamped 0..1)
  - <0.75→0; 0.75–0.85→linear→80; 0.85–0.95→linear→100; >0.95→100
- Restorative ratio = (deep_sleep_minutes + rem_sleep_minutes) / total_sleep_minutes
  - <0.20→0; 0.20–0.35→linear→100; 0.35–0.55→100; >0.55→down to ≥80
- CSS = 0.40·DurationScore + 0.30·EfficiencyScore + 0.30·RestorativeScore

## API
from physio_age.core import compute_physiological_age

compute_physiological_age(payload: Dict[str, Any]) -> Dict[str, Any]

- Required keys: `user_gender`, `sdnn_series`, `rhr_series`, and the 4 sleep raw fields
- Optional: `age_min`/`age_max` (default 20..80),
  `weights` (default {sdnn:0.45,rhr:0.20,css:0.35}), `softmin_tau` (default 0.2)

Returns:
- `physiological_age` (int), `physiological_age_weighted` (float, 1 decimal)
- `best_cost` (float), `best_age_zscores` ({z_sdnn, z_rhr, z_css})
- `window_days_used` (=30), `data_days_count`

## Examples
- Folder: `physio_age/examples/`
  - `series_usage.py` – generate a 30‑day payload and run the engine
  - `request_template.json` – input schema template
  - `sample_request.json` – a generated request
  - `sample_response.json` – the engine response saved by the example

Run example:
```
python physio_age/examples/series_usage.py
```

## Files Overview
- `physio_age/__init__.py`
  - Package entry; exports `compute_physiological_age`.
- `physio_age/core.py`
  - Main engine: loads master norms (by gender), consumes 30‑day SDNN/RHR series
    and today’s sleep raw inputs, computes CSS and physiological age.
- `physio_age/css.py`
  - CSS computation from raw sleep signals (duration/efficiency/restorative) using
    the updated piecewise rules (0.40/0.30/0.30). It first tries
    `backend.utils.sleep_metrics` for efficiency/restorative to keep one source
    of truth, and falls back to local logic if unavailable.
- `physio_age/hrv_age_table.csv`
  - Master reference for males: yearly norms (µ/σ) for SDNN, RHR, CSS by age.
- `physio_age/hrv_age_table_female.csv`
  - Master reference for females: yearly norms (µ/σ) for SDNN, RHR, CSS by age.
- `physio_age/examples/series_usage.py`
  - Generates a random 30‑day request and writes:
    - `physio_age/examples/request_template.json`
    - `physio_age/examples/sample_request.json`
    - `physio_age/examples/sample_response.json`
  - Then prints a short summary (integer and fractional physiological age).
