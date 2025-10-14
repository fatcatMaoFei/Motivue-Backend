# Architecture Overview

This document summarises the service boundaries, data contracts, and dependencies across the Motivue backend.

## Services (apps/*)

- Readiness API (`apps/readiness-api/main.py`)
  - Endpoints:
    - `POST /readiness/from-healthkit` → compute daily readiness and write `user_daily`
    - `POST /readiness/consumption` → compute training consumption and update `current_readiness_score`
    - `GET /health` → health probe
  - Depends on: `libs/readiness_engine`, `libs/core_domain/db`, `libs/training`
  - Optional: reads baseline via `BASELINE_SERVICE_URL` or local table.

- Weekly Report API (`apps/weekly-report-api/main.py`)
  - Endpoint: `POST /weekly-report/run` (LLM required) → Phase 1..5, optional persist to `weekly_reports`
  - Depends on: `libs/weekly_report`, `libs/core_domain/db`, Gemini (GOOGLE_API_KEY)

- Baseline API (`apps/baseline-api/main.py`)
  - Endpoints: `POST /api/baseline/user/{user_id}/update`, `GET /api/baseline/user/{user_id}`, analytics
  - Publishes MQ event `readiness.baseline_updated`
  - Depends on: `libs/analytics`, optional DB for baseline storage

- Physio Age API (`apps/physio-age-api/main.py`)
  - Endpoint: `POST /physio-age` → physiological age from SDNN/RHR + CSS
  - Depends on: `libs/physio/css.py`, `libs/core_domain/db` (optional read)

## Libraries (libs/*)

- readiness_engine: Bayesian readiness (engine, mapping, constants), personalization_cpt
- weekly_report: workflow orchestration, LLM provider, analysis/insights, finalizer
- training: training consumption
- analytics: baseline compute/storage/analytics
- core_domain: shared Pydantic models + SQLAlchemy models + utils
- physio: CSS computation

## Data Model (core tables)

- `user_daily(user_id, date, previous_state_probs, journal, hooper, objective, device_metrics, daily_au, final_readiness_score, current_readiness_score, final_diagnosis, final_posterior_probs, next_previous_state_probs)`
- `user_baselines(user_id, sleep_baseline_hours, sleep_baseline_eff, rest_baseline_ratio, hrv_baseline_mu, hrv_baseline_sd)`
- `user_models(user_id, model_type, payload_json, version, created_at)`
- `weekly_reports(user_id, week_start, week_end, report_version, report_payload, markdown_report, created_at)`

## Environment

- `.env` (see `.env.example`):
  - `DATABASE_URL`, `BASELINE_DATABASE_URL`
  - `GOOGLE_API_KEY`, `READINESS_LLM_MODEL`, `READINESS_LLM_FALLBACK_MODELS`
  - `RABBITMQ_URL`

## External Dependencies

- Google Gemini (JSON Mode): used in weekly report (ToT/Analyst/Communicator/Critique/Finalizer)
- RabbitMQ: Baseline service publishes `readiness.baseline_updated`
- Database: Postgres/SQLite via SQLAlchemy

## Flow (ASCII)

```
+--------------+        +------------------+        +--------------------+
|  Frontends   | -----> |  Readiness API   | -----> |   user_daily (DB)  |
+--------------+        +------------------+        +--------------------+
                               |   ^
                               v   |
                       +------------------+
                       |   training lib   |
                       +------------------+

+--------------+        +------------------+        +--------------------+
|  Scheduler   | -----> |  Baseline API    | -----> | user_baselines (DB) |
+--------------+        +------------------+        +--------------------+
                               |
                               v MQ: readiness.baseline_updated

+--------------+        +------------------+        +--------------------+
|  Frontends   | -----> | Weekly Report API| -----> | weekly_reports (DB) |
+--------------+        +------------------+        +--------------------+
                               |
                               v
                         Google Gemini
```

## Contracts (selected)

- Readiness `/readiness/from-healthkit` input: HealthKit-like daily snapshot + optional recent training AU; result includes `final_readiness_score`, `final_posterior_probs`, `next_previous_state_probs`.
- Weekly report `/weekly-report/run` input: `{ payload{history[7], recent_training_au, baselines...}, persist? }` → Phase 3 state, Phase 4 package, Phase 5 final (Markdown/chart_ids/call_to_action). LLM is mandatory.
- Baseline `/api/baseline/user/{user_id}`: returns personal baselines; update publishes MQ message with payload `{user_id, baseline}`.

