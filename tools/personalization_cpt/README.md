Personalized CPT — Tools & Usage

Purpose
- Train per-user EMISSION_CPT from daily history (CSV) and emit JSON artefacts for the readiness engine to override defaults.
- Default shrinkage strength k=50 (balanced for daily signals: Hooper/HRV/Sleep).

Layout
- tools/personalization_cpt/personalize_cpt.py — Single user: CSV → CPT JSON (k=50 by default)
- tools/personalization_cpt/monthly_update.py — Batch monthly update over a sliding window
- tools/personalization_cpt/clean_history.py — Normalize GUI/Excel exports into standard columns
- tools/personalization_cpt/PERSONALIZATION_README.md — Specification & FAQ
- samples/data/personalization/ — Input/Output artefacts (CSV/JSON/summaries)

Quick start
- Optional GUI capture
  - pip install -r gui/requirements.txt
  - streamlit run gui/app.py
  - Set CSV path in sidebar (default: samples/data/personalization/history_gui_log.csv)
- Single user training (k=50)
  - python tools/personalization_cpt/personalize_cpt.py \
    --csv samples/data/personalization/history_gui_log.csv \
    --user u001 \
    --out samples/data/personalization/personalized_emission_cpt_u001.json

Monthly batch update
- Export one CSV per user for the last 90 days into a directory (e.g., /data/readiness_exports)
- Run:
  - python tools/personalization_cpt/monthly_update.py \
    --input-dir /data/readiness_exports --since-days 90 --k 50 --user-col user_id
- Outputs into samples/data/personalization/YYYYMM/:
  - personalized_emission_cpt_<user>.json
  - monthly_summary.csv (user_id, days_used, k, path)
- Constraints: <30 days skipped; evidence with <10 valid rows keeps default.

Standard CSV columns (one row per day)
- Core: date(YYYY-MM-DD), user_id, gender(male|female)
- Training prior: training_load(none|low|medium|high|very_high)
- Sleep (posterior; either-or + keep restorative):
  - apple_sleep_score(0..100) OR sleep_performance_state(good|medium|poor)
  - restorative_sleep(high|medium|low)
- HRV (posterior): hrv_trend(rising|stable|slight_decline|significant_decline)
- Hooper (posterior): fatigue_hooper, soreness_hooper, stress_hooper, sleep_hooper (1..7)
- Others (posterior): nutrition(adequate|inadequate_*), gi_symptoms(none|mild|severe)
- Optional booleans: is_sick, is_injured, high_stress_event_today, meditation_done_today
- Missing values allowed: empty/None/NULL/NA/NaN – only valid days count for personalization.

Readiness integration (override)
- Provide `emission_cpt_override` in readiness payload; or store per-user CPT in DB and load by user_id.
- Typical persistence: table(user_id, cpt_json, trained_at, version); notify via MQ when refreshed.
