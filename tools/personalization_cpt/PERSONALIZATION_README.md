Personalized CPT — Specification & FAQ

Goal
- Take standardized daily history (CSV/DB columns) and learn a per-user EMISSION_CPT.
- Output a CPT JSON suitable for overriding the readiness engine defaults.

Core principles
- Data coverage: require ≥30 valid days overall to personalize; otherwise keep default CPT.
- Per-evidence minimums: if a specific evidence type has <10 valid samples, keep that evidence’s default distribution.
- Shrinkage: alpha = n/(n+k); default k=100 for conservative blending.
- Sleep either‑or: if `apple_sleep_score` exists (iOS26+), use it; otherwise use traditional sleep_performance (duration+efficiency). `restorative_sleep` is kept alongside Apple score.

Input columns (per day)
- date(YYYY-MM-DD), user_id, gender(male|female)
- training_load(none|low|medium|high|very_high)
- Sleep (one of): apple_sleep_score or (sleep_duration_hours + sleep_efficiency)
- restorative_ratio(0..1) optional
- hrv_trend(rising|stable|slight_decline|significant_decline)
- Hooper 1..7: fatigue_hooper, soreness_hooper, stress_hooper, sleep_hooper
- nutrition(adequate|inadequate_*), gi_symptoms(none|mild|severe)
- journal booleans: alcohol_consumed, late_caffeine, screen_before_bed, late_meal, is_sick, is_injured
- Missing allowed: empty/None/NULL/NA/NaN handled; per-evidence counts drive personalization.

CLI usage
- Single user: CSV → CPT JSON
  - python tools/personalization_cpt/personalize_cpt.py --csv samples/data/personalization/history_60d_backend.csv --user u001 --out samples/data/personalization/personalized_emission_cpt_u001.json --shrink-k 100

Output format (CPT JSON)
- Shape: { evidence_type: { category: { state: prob } } }
- Include metadata externally when storing in DB (user_id, trained_at, days_used, shrink_k, used_vars, version).

Ops considerations
- Schedule: daily/weekly jobs that re-train users with ≥30-day windows.
- Storage: relational table or object storage; record timestamps and params for audit.
- Apply: readiness service loads per-user CPT on demand; fall back to global default when missing.

FAQ
- Apple vs traditional sleep? Apple score takes precedence when available; otherwise fallback to traditional inputs.
- Why keep restorative when using Apple? The Apple score omits deep/REM breakdown; restorative signal is still useful.
- How big should k be? 50–100 works well; 50 is responsive, 100 more conservative.
