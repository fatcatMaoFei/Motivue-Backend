<details>
<summary><strong>English</strong></summary>

# Motivue Backend – Service Map

Motivue’s backend is organised as microservice entrypoints under `apps/*` and
domain libraries under `libs/*`. Each service in `apps/` can be deployed on its
own while sharing the same core Pydantic models and utilities in `libs/`.
Execution and data contracts stay independent:

- `apps/readiness-api` computes the daily readiness score (primary engine).
- `apps/weekly-report-api` generates Phase 5 weekly reports (Markdown/HTML) from
  the same readiness model + history; it does not call the readiness engine and
  writes its own outputs to DB.
- Common pattern for all services: **read from database → compute → write back /
  expose via API**. Other consumers (front-end, analytics jobs) can read stored
  JSON/Markdown without chaining services.

## Core services

| Service | What it does | Key modules | Dockerfile |
| --- | --- | --- | --- |
| Service | What it does | Key modules | Dockerfile |
| --- | --- | --- | --- |
| **Readiness API** | Daily readiness score via a Bayesian prior/posterior engine that fuses training load, objective biomarkers, subjective Hooper scores, journals, menstrual cycle and interaction terms. | `apps/readiness-api/main.py`, libs: `libs/readiness_engine/{engine.py,service.py,mapping.py,constants.py}` | `Dockerfile.readiness` |
| **Weekly Report API** | Multi-agent LLM chain that turns a hydrated `ReadinessState` into chart packs and Markdown/HTML reports (Analyst → Communicator → Critique → Finaliser) with schema validation. | `apps/weekly-report-api/main.py`, libs: `libs/weekly_report/{trend_builder.py,pipeline.py,finalizer.py}` | `Dockerfile.weekly_report` |
| **Baseline Service** | Computes and maintains long-term personal baselines (sleep duration/efficiency, restorative ratio, HRV μ/σ) with questionnaire fallbacks and auto-upgrade logic. | `apps/baseline-api/main.py`, libs: `libs/analytics/{service.py,calculator.py,storage.py,auto_upgrade.py}` | `Dockerfile.baseline` |
| **Physiological Age** | Estimates physiological age from 30-day HRV/RHR history plus today’s sleep CSS. | `apps/physio-age-api/main.py`, libs: `libs/physio/{core.py,css.py}` | `Dockerfile.physio_age` |
| **Training Consumption** | Calculates daily “consumption” points from training sessions (RPE × minutes, AU caps) to display “remaining readiness = readiness − consumption”. | libs: `libs/training/{consumption.py,factors/training.py,schemas.py}` | – |

> Weekly report logic lives under `libs/weekly_report`. The top-level package
> `weekly_report/` is a proxy to keep absolute imports stable.

### Weekly report microservice

- 启动 API：`uvicorn apps/weekly-report-api/main:app --reload`（依赖 `fastapi` 已包含在 `requirements.txt`；需要 `GOOGLE_API_KEY`）。
- 调用示例：
  ```bash
  curl -X POST http://localhost:8000/weekly-report/run \
    -H "Content-Type: application/json" \
    -d '{
          "payload": FILE_CONTENTS,
          "use_llm": true,
          "persist": true
        }'
  ```
  - `payload`：Phase 1 原始数据（含今日 raw_inputs + `history` 的 7 条 `WeeklyHistoryEntry`）。样例见 `samples/original_payload_sample.json`。
  - LLM：服务端强制走 LLM 路径；需提供 `GOOGLE_API_KEY`（可选 `READINESS_LLM_MODEL`、`READINESS_LLM_FALLBACK_MODELS`）。
  - `persist=true`：调用结束后将 Phase 5 结果写入 `weekly_reports` 表（定义在 `api/db.py`，默认使用 `.env` 的 `DATABASE_URL`）。
- 返回值同时包含 Phase 3 `ReadinessState` JSON、Phase 4 `WeeklyReportPackage`、Phase 5 `WeeklyFinalReport`（含 Markdown/HTML/图表 ID）。

#### Weekly report payload quick reference

- **Raw inputs（今日快照，可选）**：睡眠分钟、HRV 日值/滚动均值、Hooper、`journal` 布尔位与 `lifestyle_tags[]`（支持前缀，如 `sport:tennis`、`strength:legs`）、自由备注 `report_notes`。这些字段映射到 `ReadinessState.raw_inputs.*`，除滚动均值外都可缺省。
- **History（近 7 天必填）**：`payload.history` 需要提供 `WeeklyHistoryEntry[]`，每条含 `date`、`readiness_score / readiness_band`、`hrv_rmssd / hrv_z_score`、`sleep_duration_hours / sleep_deep_minutes / sleep_rem_minutes`、`daily_au`、`hooper`、`lifestyle_events[]`。周报的表格和趋势完全基于此数组。
- **Recent training AU（近 28 天）**：`recent_training_au` 用于 ACWR（EWMA7/EWMA28）；缺失时 ACWR 即返回 `None`。
- **No training_sessions required**：日训练细项不是必填；如需为后续洞察/Planner 提供“训练类型/部位”，可在 `journal.lifestyle_tags[]` 或未来的 `training_sessions.type_tags[]` 中使用 `sport:` / `strength:` 前缀，聚合时透传到 `history[].lifestyle_events[]`。

#### Payload v2 (optional training fields / 可选训练字段)
- Purpose 目的：无需图表也能让 LLM 写出“训练内容回顾”。未提供时，服务端会基于 `user_id` 自动从 DB 聚合补全。
- Fields 字段：
  - `training_tag_counts`: 按标签聚合的 7 天与 30 天次数（例如 `strength:chest`、`cardio:rower`、`sport:tennis`）。
  - `strength_levels`: 按动作提供两点（`latest` 与 `baseline_30d`），包含 `{date, weight_kg, reps, one_rm_est}`，便于对比进步/停滞。

Example 示例：
```jsonc
{
  "training_tag_counts": {
    "strength:chest": {"7d": 1, "30d": 8},
    "cardio:rower": {"7d": 1, "30d": 4},
    "sport:tennis": {"7d": 0, "30d": 3}
  },
  "strength_levels": {
    "bench_press": {
      "latest": {"date":"2025-10-14","weight_kg":100,"reps":3,"one_rm_est":110.0},
      "baseline_30d": {"date":"2025-09-14","weight_kg":90,"reps":3,"one_rm_est":99.0}
    }
  }
}
```

#### Weekly report output quick reference

- Phase 3：`phase3_state`（包含 `metrics`、`insights`、`next_week_plan`）。
- Phase 4：`package`（图表 `charts[]`、Analyst/Communicator 文稿、批注）。
- Phase 5：`final_report` (`WeeklyFinalReport`)：`markdown_report`、可选 `html_report`、`chart_ids`、`call_to_action`。
- Markdown 会在固定位置插入图表锚点 `[[chart:<id>]]`（训练负荷、HRV、睡眠、Hooper、生活方式）；前端按锚点替换成 `package.charts[]` 中的图表组件。
- Planner（Phase 3B）生成 `next_week_plan`：周目标、监测阈值、原则、分日强度/AU 区间。Finalizer 与 LLM 均能看到该结构，Markdown 里的“下周行动计划”已展示这些信息。


## Directory guide

| Path | Purpose | Highlights |
| --- | --- | --- |
| `api/` | Legacy FastAPI wrapper that glues readiness + baselines for internal demos. | `api/main.py`, simple DB helpers. |
| `backend/` | Shared utilities. Currently hosts the sleep quality helper used by readiness & physiological-age CSS. | `backend/utils/sleep_metrics.py` (`compute_sleep_metrics` returns efficiency & restorative ratio). |
| `baseline/` | Baseline microservice (see above). | README + API/Deployment guides. |
| `baseline_analytics/` | Windowed comparisons (today vs baseline, recent vs previous) independent of the readiness engine. | `compare_today_vs_baseline`, `compare_recent_vs_previous`. |
| `docs/` | Design notes and backend integration guides (e.g. weekly report backend notes, prompt plans). | `weekly_report_backend_notes.md`, PDFs. |
| `docs/weekly_report_frontend_notes.md` | Front-end integration cheatsheet for weekly report API / payloads. | – |
| `gui/` | Prototype UIs and demo assets. | – |
| `physio_age/` | Physiological age engine (see above). | Example scripts + master tables. |
| `readiness/` | Readiness engine, rule-based insights, mapping helpers, Hooper/ACWR tools. | `readiness/engine.py`, `readiness/mapping.py`, `readiness/constants.py`. |
| `weekly_report/` | Weekly report service (charts, workflow, multi-agent chain, finaliser). | `weekly_report/state.py`, `weekly_report/models.py`, `weekly_report/trend_builder.py`, `weekly_report/pipeline.py`, `weekly_report/workflow/graph.py`, `weekly_report/finalizer.py`. |
| `samples/` | Regression artefacts and example outputs. | `weekly_report_sample.json`, `weekly_report_final_sample.md`, `readiness_state_report_sample.json`. |
| `scripts/` | Operational helpers. | `scripts/db_check.py`. |
| `training/` | Training consumption module (see above). | Example configs under `training/factors/`. |
| `tmp/` | Scratch space (ignored by git). | – |
| `tools/personalization_cpt/` | Experiments around personalised emission CPTs (batch scripts, artefacts). | `personalize_cpt.py`, outputs under `samples/data/personalization/`. |
| `docs/backend/` | Backend documentation (microservice integration, deployment, iOS26 migration, baseline plans). | `microservices_integration.md`, etc. |

## Notable documents & samples

- `docs/weekly_report_backend_notes.md` – backend integration plan for Phase 4/5 weekly reports.  
- `readiness_state_plan.txt` – five-phase readiness roadmap.  
- `samples/weekly_report_final_sample.*` – Markdown/JSON produced by finaliser.  
- `AI_prompt_doc.txt`, `S&C周报LLM流程优化.pdf`, `运动科学数据洞察生成.pdf` – prompt design and research decks.

## Running the services

```bash
# Build individual microservice images
docker build -f Dockerfile.readiness -t motivue-readiness .
docker build -f Dockerfile.baseline   -t motivue-baseline .
docker build -f Dockerfile.physio_age -t motivue-physio-age .
docker build -f Dockerfile.weekly_report -t motivue-weekly-report .

# Sample scripts
python readiness/examples/simulate_days_via_service.py
python physio_age/examples/series_usage.py
python samples/generate_weekly_report_samples.py
```

## Usage & implementation notes

### System data flow (high level)

1. **Ingestion** → raw inputs (`ReadinessState.raw_inputs`) including sleep, HRV, Hooper, journal, training and optional `report_notes`.
2. **Deterministic metrics** → `metrics_extractors.populate_metrics` writes ACWR, HRV z-score, sleep deltas, personalised thresholds.
3. **Bayesian engine** → `service.compute_readiness_from_payload` orchestrates prior/posterior updates and outputs daily readiness score + audit.
4. **Rule-based insights** → `insights/rules.generate_insights` adds deterministic alerts (ACWR high/low, sleep efficiency drop, HRV decline, lifestyle flags, etc.).
5. **Weekly report** → multi-agent LLM pipeline (separate `weekly_report/` package) creates narratives and final Markdown/HTML.
6. **Supporting services** → baseline service feeds personalised thresholds; physiological age engine and training consumption provide auxiliary scores.

### Readiness engine (Bayesian prior/posterior)

#### Inputs & payload schema
- **States**: `['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']`.
- **Essential fields**: `user_id`, `date`, `gender`, `previous_state_probs` (optional), `training_load`, `recent_training_loads` or `recent_training_au`, Hooper scores (`hooper: {fatigue,soreness,stress,sleep}`), objective evidence (`sleep_*`, `hrv_*`, `nutrition`, `gi_symptoms`, `fatigue_3day_state`), journal flags (`journal`), `cycle`.
- **Optional**: `report_notes` (free text for weekly report), personalised emission CPT overrides.

#### Prior calculation (see `readiness/engine.py`)
1. **Baseline transition**: `BASELINE_TRANSITION_CPT` gives P(state_today | state_yesterday).
2. **Training load CPT** (`TRAINING_LOAD_CPT`) + `CAUSAL_FACTOR_WEIGHTS['training_load']`.
3. **Streak penalty**: consecutive high loads (≥3 of last 4, ≥6 of last 8) shift probability towards `NFOR`.
4. **ACWR & short-term fatigue** (`_apply_acwr_and_fatigue3`):
   - Compute A7/C28 ratios from AU.
   - Reward if R7/28 ≤ 0.9 (shift mass to `Well-adapted`/`Peak`).
   - Penalty if R7/28 ≥ 1.15 with severity scaling (`low/mid/high` band, R3/28 boost).
   - DOMS & energy proxies modulate `Acute Fatigue`.
5. **Journal yesterday**: alcohol, late caffeine, screen, late meal multiply prior by respective CPT; persistent flags (sick/injured) are inherited into today’s journal store but only act in posterior.
6. **Normalisation** ensures prior sums to 1.

#### Posterior update
1. **Evidence pool**: merge carried journal flags + new evidence, feed into `mapping.map_inputs_to_states`.
2. **Hooper continuous likelihood** (`hooper_to_state_likelihood`):
   - Each numeric score maps to low/medium/high anchor, exponent α per score (e.g., fatigue 3→α0.4, fatigue 7→α1.5).
   - Likelihood raised to `EVIDENCE_WEIGHTS_FITNESS[var]`.
3. **Categorical evidence**: multiply by emission CPT row for each mapped variable (sleep performance, restorative sleep, HRV trend, nutrition, GI symptoms, fatigue_3day_state, Apple sleep score etc.).
4. **Interaction CPT** (`INTERACTION_CPT_SORENESS_STRESS`) handles soreness×stress combinations.
5. **Menstrual cycle**: for female users, `cycle` or `cycle_day` feeds continuous likelihood using personal params if available.
6. **Score**: readiness score = round(Σ posterior[state] × `READINESS_WEIGHTS[state]`).
7. **Outputs**: posterior probs, score, diagnosis, `update_history` (timestamped evidence list), `next_previous_state_probs`.

#### Mapping nuances (`readiness/mapping.py`)
- **Apple sleep score** gate: when `ios_version>=26` and `apple_sleep_score` present, skip traditional sleep performance mapping.
- **Sleep thresholds**: personalised durations based on `sleep_baseline_hours`; efficiency thresholds optionally personalised via `PERSONALIZE_SLEEP_EFFICIENCY`.
- **HRV trend**: primary path uses z-score (`hrv_rmssd_today - μ)/σ`), fallback uses 3 vs 7-day delta.
- **Hooper**: stores both categorical band (`subjective_*`) and numeric score (`*_score`) for continuous likelihood.
- **Booleans**: `is_sick`, `is_injured`, `high_stress_event_today`, `meditation_done_today` pass through.

#### Journals & personalisation
- Journal manager auto-clears yesterday’s short-term flags after use, but carries persistent status.
- Personalised CPT overrides can be provided in payload (e.g., per user emission CPT).
- Personalised CPT tools are under `tools/personalization_cpt/`; integrate by passing `emission_cpt_override`.

### Weekly report pipeline (multi-agent LLM)

#### Inputs
- Hydrated `ReadinessState`（可由 readiness API 或缓存生成的 `state.json`）。
- History list of `WeeklyHistoryEntry` (7 or 28 days) including readiness score/band, HRV, sleep metrics, AU, Hooper, lifestyle events.
- Optional `report_notes` (coach/athlete comments).

#### Process (defined in `weekly_report/pipeline.py` + `weekly_report/llm/provider.py`)
1. **Trend builder**: `build_default_chart_specs` summarises trends into ChartSpec objects (line, combo, radar, scatter).
2. **LLM provider** (`GeminiProvider`):
   - Uses **JSON schema** enforcement and system prompts for stability.
   - **Analyst agent**: composes summary points, risks, opportunities, chart references. Schema ensures arrays/fields present.
   - **Communicator agent**: converts analyst report + charts + notes into Markdown sections (`本周亮点` / `风险观察` / `建议与行动`), tone tags.
   - **Critique agent**: audits analyst + communicator for coverage, evidence quality, conflict logic, actionability; returns structured issues.
   - **Fallback heuristics**: when LLM fails, deterministic analyst/communicator functions produce safe outputs.
3. **Finaliser** (`weekly_report/finalizer.py`):
   - Consolidates analyst + communicator + history to produce Markdown/HTML (`WeeklyFinalReport`), with call-to-action list and chart ID ordering.
4. **Outputs**:
   - `WeeklyReportPackage` (charts + analyst + communicator + optional critique).
   - `WeeklyFinalReport` (markdown/html + chart list + CTA) when finaliser is called.

#### Five-stage architecture (per design PDFs)
Drawing from *AI教练提示词与架构优化.pdf* 与 *智能体功能与商业模式优化.pdf*，`weekly_report/` 采用“主管-专家”LangGraph 架构，拆成五个阶段：

| Stage | 作用 | 输入示例 | 输出示例 |
| --- | --- | --- | --- |
| **Phase 1 数据拉取** | 从数据库或缓存读取最近 7/28 天的准备度、HRV、睡眠、训练、Hooper、生活方式事件，外加 `report_notes` 与训练日志。 | 原始 `user_daily` 行、`weekly_history` 视图 | Python dict / dataframe 集合（raw metrics）。 |
| **Phase 2 特征与聚合** | 清洗缺失值、计算滚动指标（ACWR、连续高负荷、睡眠恢复性、HRV z-score 等），补充生活方式标签与训练摘要。 | Phase 1 输出 | 结构化特征包（dict），供洞察/LLM 使用。 |
| **Phase 3 洞察装配** | 规则/统计分析生成 JSON 洞察：训练超量、睡眠下降 vs 生活方式、主客观冲突、恢复速率等；同时整理成统一 schema。 | 特征包 + 原始历史 | `state.insights` 风格的 JSON（含 summary、evidence、actions）。 |
| **Phase 4 多智能体 LLM** | 主管智能体调度 Analyst → Communicator → Critique（LangGraph），使用上阶段 JSON + chart specs + report notes 写出结构化文本。 | Phase 3 洞察 + chart specs + notes | `WeeklyReportPackage`：summary_points、risks、opportunities、sections、issues。 |
| **Phase 5 Finalizer** | 将多智能体输出与历史记录、训练日志整合为 Markdown/HTML 成品，并附 CTA、chart_id 顺序。 | `WeeklyReportPackage` + history + notes | `WeeklyFinalReport`（Markdown/HTML + chart_ids + call_to_action）。 |

> **提示**：阶段间所有数据均采用 JSON Schema 管控，方便在 LangGraph 中序列化与回放；主管-专家模式确保只有唯一写入通道（Finalizer），符合设计文档的鲁棒性要求。

#### Running sample
```bash
python samples/generate_weekly_report_samples.py \
  --state samples/readiness_state_report_sample.json \
  --history samples/history_week.json
```
Produces Phase 4 JSON (`weekly_report_sample.json`) and final markdown (`weekly_report_final_sample.md`).

### Repository layout (monorepo)

- `apps/` — FastAPI entrypoints: readiness-api, baseline-api, physio-age-api, weekly-report-api
- `libs/` — shared libraries: readiness_engine, weekly_report, analytics, core_domain, physio
- `weekly_report/` — top-level proxy package pointing to `libs/weekly_report` (absolute imports kept stable)
- `readiness/` — top-level proxy package pointing to `libs/readiness_engine` (legacy imports remain valid)
- `samples/` — runnable examples and generated outputs
- `tools/personalization_cpt/` — CLI tools for personalized CPT training
- `docs/backend/` — backend guides (migration, deployment, integration)
- `docs/refs/` — design PDFs and business/reference notes

See also: `docs/backend/architecture_overview.md` for service boundaries, contracts, and dependencies.

### Directory Reference (what each module does)

- `apps/`
  - `apps/readiness-api/main.py`: HTTP API for daily readiness. Ingests HealthKit-like payload, merges baselines, calls readiness engine, writes `user_daily` and supports `POST /readiness/consumption` for training consumption updates.
  - `apps/weekly-report-api/main.py`: HTTP API for weekly report generation (LLM required). Runs workflow (ToT/Critique), builds chart specs, Analyst/Communicator, Finalizer, and optionally persists `weekly_reports`.
  - `apps/baseline-api/main.py`: HTTP API for baseline compute/update and retrieval; publishes MQ message `readiness.baseline_updated` so readiness can refresh personalization state.
  - `apps/physio-age-api/main.py`: HTTP API for physiological age (uses SDNN/RHR + CSS).

- `libs/`
  - `libs/readiness_engine/`
    - `engine.py`: ReadinessEngine core (Bayesian prior/posterior, journal manager).
    - `mapping.py`: Maps raw numeric/enum inputs (sleep/HRV/Hooper/training) into engine evidence.
    - `constants.py`: Global CPT tables and thresholds.
    - `service.py`: Thin façade `compute_readiness_from_payload(...)` used by API and tools.
    - `personalization_cpt/train.py`: Library entry to learn per-user EMISSION_CPT from CSV/history.
    - `personalization_simple.py`: Simple personalization helpers (demo/data generation, load personalized CPT into constants).
  - `libs/weekly_report/`
    - `workflow/graph.py`: Orchestrates ingest → metrics → insights → complexity → ToT → Critique → Revision → Planner.
    - `pipeline.py`: Builds charts + LLM outputs (Analyst/Communicator/Critique) with fallbacks.
    - `finalizer.py`: Produces Markdown report + chart IDs + CTA.
    - `llm/provider.py`: Gemini provider, prompts and JSON schema enforcement.
    - `analysis/*`: Statistical summaries and correlations for history windows.
    - `insights/*`: Rule-based insights and tags.
    - `trend_builder.py`: Generates ChartSpec payloads for frontend.
  - `libs/analytics/`
    - `service.py`: Baseline service entrypoints and integration helpers.
    - `storage.py`: Storage backends (in-memory/file/SQLAlchemy) for baselines.
    - `daily_vs_baseline.py`: Comparisons for analytics dashboards.
  - `libs/core_domain/`
    - `models.py`: Shared Pydantic models (ChartSpec, WeeklyReportPackage, WeeklyFinalReport, etc.).
    - `db.py`: SQLAlchemy models (`user_daily`, `user_baselines`, `weekly_reports`) and `init_db()`.
    - `utils/sleep.py`: Sleep efficiency/restorative ratio helpers.
  - `libs/physio/css.py`: Composite Sleep Score (CSS) computation.

- `weekly_report/`: Top-level proxy package pointing to `libs/weekly_report` so absolute imports `weekly_report.*` remain stable.
- `readiness/`: Top-level proxy package pointing to `libs/readiness_engine` so legacy imports remain valid.

- `libs/training/`
  - Purpose: A small domain library used by readiness API to compute daily training consumption and update "current_readiness_score" for display.
  - Files: `consumption.py` (entry `calculate_consumption`), `factors/training.py` (piecewise curves), `schemas.py` (payload models), `__init__.py` (exports).

- `tools/personalization_cpt/`
  - `personalize_cpt.py`: Single-user CSV → CPT JSON.
  - `monthly_update.py`: Batch per-user CPT updates over recent N days; outputs under `samples/data/personalization/YYYYMM/`.
  - `batch_personalize_and_compare.py`: Generate 60/100/200d variants and compare deltas to global CPT.
  - `clean_history.py`: Normalize GUI/Excel CSV into standard columns.
  - `apply_cpt.py`: Load a CPT JSON into runtime (`constants.EMISSION_CPT`) for experimentation.

- `samples/`
  - Example payloads for readiness/weekly report and generated Phase 4/5 outputs (`weekly_report_final_sample.*`).
  - `samples/data/personalization/`: CSV inputs and generated personalized CPT artefacts.

- `docs/backend/`: Backend guides (migration, deployment, integration).  
  `docs/refs/`: Design PDFs and reference TXT files (centralized).

- `infra/compose/docker-compose.yml` and `infra/docker/*`: Container builds and local orchestration.

- `tmp/`: Scratchpad folder for local experiments; ignored by services. Safe to clean.
- `legacy_personalization/`: Temporary placeholder of the old Chinese-named folder; no code references it. Safe to remove once the team confirms migration is complete.

### Housekeeping & migrations

- Removed all Chinese-named folders in repo structure; moved prior `后端文档/` to `docs/backend/` with English file names.
- Consolidated PDFs and TXT references under `docs/refs/`.
- Normalized personalized CPT scripts under `tools/personalization_cpt/`; artefacts live in `samples/data/personalization/`.
- Unified imports to use `weekly_report.*` in apps; compatibility proxies are preserved.

### Baseline service (personal thresholds)

1. **Data requirements**: ideally ≥30 days of sleep duration/efficiency + HRV RMSSD. Accepts raw HealthKit events or aggregated daily values.
2. **Default bootstrapping**:
   - Questionnaire results map to archetypes (`short_sleeper`, `normal`, `long`; `high_hrv`, `normal`, `low`).
   - `default_baselines.py` holds archetype parameters.
3. **Full computation** (`compute_baseline_from_healthkit_data`):
   - Cleans data (outlier removal, min coverage).
   - Computes means (sleep hours, efficiency, restorative ratio, HRV μ/σ).
   - Emits `BaselineResult` with metadata (status: success_success_with_defaults / insufficient_data).
4. **Incremental vs full updates**:
   - `auto_upgrade.update_baseline_if_needed` checks last update timestamp, data coverage, quality score to decide:
     - 7-day incremental update (smoothed blend).
     - 30-day full recompute.
5. **Endpoints** (`baseline/api.py`):
   - `POST /baseline/calculate`
   - `POST /baseline/update`
   - `GET /baseline/{user_id}`
   - Storage implementations: memory, file, SQLite (`baseline/storage.py`).
6. **Integrating with readiness**: inject results into payload fields (`sleep_baseline_hours`, `sleep_baseline_eff`, etc.) so mapping functions use personalised thresholds.

### Physiological age engine

1. **Inputs**:
   - `user_gender` (male/female).
   - `sdnn_series` (≥30 values, ms) & `rhr_series` (≥30 values, bpm).
   - Today’s sleep: `total_sleep_minutes`, `in_bed_minutes`, `deep_sleep_minutes`, `rem_sleep_minutes`.
   - Optional `age_min`, `age_max`, `weights` (`sdnn`, `rhr`, `css`), `softmin_tau`.
2. **CSS computation** (`physio_age/css.py`):
   - Duration score: piecewise (0 below 4h, 100 at 7–9h, etc.).
  - Efficiency score: uses sleep efficiency (siamesed with `backend/utils/sleep_metrics`).
   - Restorative score: deep + REM ratio (0–100).
   - CSS = 0.40·Duration + 0.30·Efficiency + 0.30·Restorative.
3. **Age search** (`physio_age/core.py`):
   - Load µ/σ tables (`hrv_age_table.csv`, `hrv_age_table_female.csv`).
   - For each age: z-scores for SDNN, RHR (sign inverted so higher better), CSS.
   - Cost = 0.45·z_sdnn² + 0.20·z_rhr² + 0.35·z_css² (defaults configurable).
   - **Output**: integer age (min cost), `physiological_age_weighted` (soft-min), diagnostic bundle (`best_age_zscores`, `window_days_used`, `data_days_count`).

### Training consumption (readiness subtraction)

1. **Input**: `training_sessions` with `rpe`, `duration_minutes`, optional `au`, `label`, `session_id`.
2. **Session AU**:
   - Priority: explicit `au` → `rpe × duration` → label default (无/低/中/高/极高 mapped to {0,200,350,500,700}).
3. **Piecewise curve** (see `training/factors/training.py`):
   - AU ≤150 → 0–5
   - 150–300 → 5–12
   - 300–500 → 12–25
   - >500 → 25–40 (saturates ~900)
   - Clipped by `cap_session` (default 40).
4. **Daily total**:
   - Sum capped by `cap_training_total` (default 60).
   - Returns `consumption_score`, optional `display_readiness = base_readiness_score - round(consumption_score)`, per-session breakdown, caps applied, params used.
5. **Extensions**: architecture allows adding new factors (journal, device metrics) by appending to `training/factors/`.

### Baseline analytics (trend comparison)

1. **Today vs baseline** (`compare_today_vs_baseline`):
   - Input arrays (latest value = today) for sleep hours, efficiency, restorative ratio, HRV RMSSD, training AU.
   - For each window N (default 7/28/56): compare today vs mean of previous N days.
   - Returns change %, up/down/flat flags, optional override comparisons to supplied baselines.
2. **Recent vs previous** (`compare_recent_vs_previous`):
   - Recent N-day average vs previous N (or mapped window).
   - Same metrics & outputs as above.
3. **Use cases**: heuristics for dashboards, triggers for insights or LLM context.

### Personalised CPT experiments (`tools/personalization_cpt/`)

- Scripts to fit custom emission CPTs from historical labelled data (`personalize_cpt.py`, `monthly_update.py`, `batch_personalize_and_compare.py`).
- Artefacts stored under `samples/data/personalization/`.
- Inject via readiness payload (`emission_cpt_override`).

### Multi-service integration

- `infra/compose/docker-compose.yml` links readiness ↔ baseline ↔ physio age, enabling readiness service to call baseline/physio age APIs.
- `docs/backend/microservices_integration.md` details service discovery, MQ topics, and data contracts.
- `API/main.py` offers a simple aggregate service for demos (ingest data, call readiness, store results).

</details>

<details open>
<summary><strong>中文说明</strong></summary>

# Motivue 后端服务总览

整体结构采用“应用入口 apps/* + 领域库 libs/*”的企业化分层：
- apps/*：每个子目录是一个可独立部署的微服务入口（FastAPI）。
- libs/*：可复用的领域逻辑与模型（评分引擎、周报流水线、训练消耗、基线、通用模型等）。

各服务共享同一套 Pydantic 模型与工具，但 **运行流程、接口、落库策略互相解耦**。
通用模式为：**从数据库取数 → 计算 → 写回数据库 / 暴露 API**。前端与其他后台只需读取已落库的 JSON/Markdown，无需串联多个服务。

## 核心服务

| 服务 | 功能概述 | 关键模块 | Dockerfile |
| --- | --- | --- | --- |
| **准备度 API** | 采用贝叶斯先验/后验模型，融合训练负荷、客观生理信号、Hooper 主观评分、Journal、月经周期，生成每日准备度。 | `apps/readiness-api/main.py`；libs：`libs/readiness_engine/{engine.py,service.py,mapping.py,constants.py}` | `Dockerfile.readiness` |
| **周报 API** | 多智能体 LLM 的周报生成链路（Analyst → Communicator → Critique → Finalizer），生成图表配置与 Markdown/HTML（强制 LLM）。 | `apps/weekly-report-api/main.py`；libs：`libs/weekly_report/{trend_builder.py,pipeline.py,finalizer.py}` | `Dockerfile.weekly_report` |
| **基线服务** | 计算/维护个性化基线（睡眠/HRV），支持问卷兜底与自动升级。 | `apps/baseline-api/main.py`；libs：`libs/analytics/{service.py,calculator.py,storage.py,auto_upgrade.py}` | `Dockerfile.baseline` |
| **生理年龄服务** | 基于 30 天 HRV/RHR 与当日 CSS 的生理年龄估计。 | `apps/physio-age-api/main.py`；libs：`libs/physio/{core.py,css.py}` | `Dockerfile.physio_age` |
| **训练消耗** | 计算“当日训练消耗分”，用于展示“当前剩余准备度”。 | libs：`libs/training/{consumption.py,factors/training.py,schemas.py}` | – |

> 周报核心逻辑位于 `libs/weekly_report`；顶层 `weekly_report/` 包是代理，仅用于保持绝对导入稳定。

## 目录速览

| 路径 | 作用 | 重点文件 |
| --- | --- | --- |
| `apps/` | 微服务入口（FastAPI）。 | `apps/readiness-api/main.py`、`apps/weekly-report-api/main.py`、`apps/baseline-api/main.py`、`apps/physio-age-api/main.py` |
| `libs/readiness_engine/` | 准备度引擎（先验/后验/映射/常量）+ 个性化 CPT 训练库。 | `engine.py`、`service.py`、`mapping.py`、`constants.py`、`personalization_cpt/train.py` |
| `libs/weekly_report/` | 周报工作流、LLM 代理、分析/洞察、Finalizer、图表。 | `workflow/graph.py`、`pipeline.py`、`finalizer.py`、`llm/provider.py`、`trend_builder.py` |
| `libs/training/` | 训练消耗计算模块（供 readiness API 使用）。 | `consumption.py`、`factors/training.py`、`schemas.py` |
| `libs/analytics/` | 基线计算/存储/分析。 | `service.py`、`storage.py`、`daily_vs_baseline.py` |
| `libs/core_domain/` | 共享 Pydantic/SQLAlchemy 模型与通用工具。 | `models.py`、`db.py`、`utils/sleep.py` |
| `libs/physio/` | CSS 与生理年龄相关实现。 | `css.py`、`core.py` |
| `weekly_report/` | 代理包，指向 `libs/weekly_report`（兼容历史绝对导入）。 | `weekly_report/__init__.py` |
| `readiness/` | 代理包，指向 `libs/readiness_engine`（兼容历史绝对导入）。 | `readiness/__init__.py` |
| `tools/personalization_cpt/` | 个性化 CPT CLI 工具与脚本。 | `personalize_cpt.py`、`monthly_update.py`、`clean_history.py` |
| `samples/` | 样例与生成产物（含个性化数据）。 | `samples/weekly_report_final_*`、`samples/data/personalization/` |
| `docs/backend/` | 后端文档（集成/部署/迁移/基线计划等）。 | `ios26_migration_guide.md`、`microservices_integration.md` |
| `docs/refs/` | 设计 PDF/TXT 资料（集中索引）。 | `docs/refs/INDEX.md` |
| `infra/compose/` | Compose 编排。 | `infra/compose/docker-compose.yml` |
| `infra/docker/` | 各服务 Dockerfile。 | `infra/docker/Dockerfile.*` |
| `tmp/` | 临时目录（不参与服务）。 | – |

## 关键文档与样例

- `docs/backend/weekly_report_backend_notes.md`：周报 Phase 4/5 后端集成指南。  
- `docs/backend/architecture_overview.md`：服务边界/契约/依赖图与环境说明。  
- `samples/weekly_report_final_sample.*`：Finalizer 生成的 Markdown/JSON。  
- `docs/refs/`：提示词与研究资料的 PDF/TXT 汇总（见 `docs/refs/INDEX.md`）。

## 服务运行方式

### 本地（单服务）
```bash
pip install -r requirements.txt
export GOOGLE_API_KEY=你的Key
uvicorn apps/weekly-report-api/main:app --reload
```

### Docker Compose（多服务）
```bash
# 在 .env 中设置 DATABASE_URL 与 GOOGLE_API_KEY（参考 .env.example）
docker compose -f infra/compose/docker-compose.yml up -d
```

## 使用方法与实现细节

### 系统整体流程

1. **数据摄入**：构建 `ReadinessState.raw_inputs`（睡眠、HRV、Hooper、Journal、训练、自由备注等）。
2. **确定性指标**：`metrics_extractors.populate_metrics` 计算 ACWR、连续高强、睡眠/HRV 指标并写入 `state.metrics`。
3. **贝叶斯引擎**：`service.compute_readiness_from_payload` 生成当日准备度分数、后验概率和审计日志。
4. **规则洞察**：`insights/rules.generate_insights` 生成 ACWR 高/低、睡眠效率下降、HRV 下降、生活方式事件等结构化提醒。
5. **周报生成**：多智能体 LLM 流水线（`weekly_report/` 模块）产出图表、分析稿、教练稿与最终 Markdown/HTML。
6. **辅助服务**：基线服务提供个体阈值；生理年龄与训练消耗作为附加指标；基线分析用于趋势对比。

### 准备度引擎（先验/后验）

#### 输入与状态
- 状态集合：`['Peak','Well-adapted','FOR','Acute Fatigue','NFOR','OTS']`。
- 主要字段：`previous_state_probs`、`training_load`、`recent_training_loads`/`recent_training_au`、Hooper 四项、客观证据（`sleep_*` / `hrv_*` / `nutrition` / `gi_symptoms` / `fatigue_3day_state`）、`journal`、`cycle`、`report_notes`。

#### 先验计算（详见 `libs/readiness_engine/engine.py`）
1. **状态转移**：`BASELINE_TRANSITION_CPT` 计算昨日→今日的基础概率。
2. **训练负荷**：`TRAINING_LOAD_CPT` × `CAUSAL_FACTOR_WEIGHTS['training_load']` 调整先验。
3. **连续高强惩罚**：最近 4/8 天高强度次数触发概率向 `NFOR` 偏移（0.5 或 0.6）。
4. **ACWR 与短期疲劳**：
   - 计算 AU 滑窗均值（A7、C28、A3）。
   - R7/28 ≤0.9 → 奖励（向 `Peak`/`Well-adapted` 转移）。
   - R7/28 ≥1.15 → 惩罚（向 `Acute Fatigue`/`NFOR` 转移），严重度与慢性负荷、R3/28 相关。
   - DOMS + Energy 与 AU 归一指标构成疲劳得分，控制 `Acute Fatigue`。
5. **昨天 Journal**：酒精、晚咖、屏幕、晚餐使用对应 CPT 乘权；生病/受伤继承到今日的 evidence pool，但不影响先验。

#### 后验更新（详见 `libs/readiness_engine/*`）
1. **证据映射**：`mapping.map_inputs_to_states` 将原始数据转换为枚举或连续打分，处理苹果睡眠评分、HRV z 分数等。
2. **Hooper 连续似然**：`hooper.hooper_to_state_likelihood` 根据分数选定锚点并按 α 指数放大（1..7 对应不同 α），再乘以权重。
3. **离散证据**：`EMISSION_CPT[var][value]` × `EVIDENCE_WEIGHTS_FITNESS[var]` 更新后验。
4. **交互项**：酸痛×压力组合使用 `INTERACTION_CPT_SORENESS_STRESS`。
5. **月经周期**：女性调用 `cycle_like_params` 或 `cycle_likelihood_by_day` 计算连续似然。
6. **评分**：`final_readiness_score = round(sum(posterior[state] * READINESS_WEIGHTS[state]))`，输出诊断、后验、更新历史。

#### 关键实现细节
- **Apple 睡眠评分**：`ios_version>=26` 时启用五档 `apple_sleep_score`（excellent/good/fair/poor/very_poor），并阻断传统睡眠表现枚举。
- **睡眠阈值**：基于 `sleep_baseline_hours` 和 `sleep_baseline_eff` 个性化，支持开关 `PERSONALIZE_SLEEP_EFFICIENCY`。
- **HRV 映射**：优先使用 `(today - μ) / σ`，备选 3 vs 7 日增幅。
- **Hooper**：数值与枚举共存，保障后验可同时使用连续与离散证据。
- **个人化 CPT**：可通过 payload 的 `emission_cpt_override` 注入，或使用 `tools/personalization_cpt/` 工具训练产生。

### 周报流水线（多智能体 LLM）

#### 输入
- 完整的 `ReadinessState`（包含洞察、raw_inputs、metrics、report_notes）。
- `WeeklyHistoryEntry` 列表（含准备度分数/分档、HRV、睡眠、训练、Hooper、生活方式事件）。

#### 流程
1. **趋势图构建**：`weekly_report.trend_builder.build_default_chart_specs` 输出准备度趋势、准备度×HRV、HRV Z 分、睡眠结构、训练 AU、Hooper 雷达、生活方式时间线等 ChartSpec。
2. **LLM 代理链**（配置在 `weekly_report/llm/provider.py`）：
   - **Analyst**：生成 summary_points / risks / opportunities / chart_ids（严格 JSON Schema）。
   - **Communicator**：将分析结果转换成 Markdown 段落，输出语气标签与行动清单。
   - **Critique**：检查覆盖面、证据准确性、主客观冲突与行动性，返回结构化问题。
   - 任何阶段失败都会写入日志并回退到 heuristic 输出，确保稳定。
3. **Finalizer**：`weekly_report/finalizer.generate_weekly_final_report` 整合分析/沟通稿与历史数据，生成 Markdown+HTML、调用前端可直接渲染。

#### 输出
- `WeeklyReportPackage`：charts + analyst + communicator + critique（可空）。
- `WeeklyFinalReport`：Markdown/HTML、图表顺序、CTA 列表。
- 示例脚本会把中间结果和最终 Markdown 写入 `samples/`。

### 基线服务

1. **问卷兜底**：数据不足时，根据睡眠/HRV 类型（问卷）使用 `default_baselines` 生成初始阈值。
2. **基线计算**：
   - `compute_baseline_from_healthkit_data` 清洗 30 天数据，计算睡眠时长均值、效率、恢复性比例、HRV 均值/标准差。
   - 返回状态（成功 / 默认基线 / 数据不足）及元信息。
3. **自动升级**：
   - `update_baseline_if_needed` 依据上次更新时间、数据覆盖率、质量评分决定“7 天增量”或“30 天重算”，结果交给 `baseline/storage`（内存/文件/SQLite）。
4. **对接准备度**：在 readiness payload 中填 `sleep_baseline_hours`、`sleep_baseline_eff`、`rest_baseline_ratio`、`hrv_baseline_mu`、`hrv_baseline_sd`，映射层自动使用。

### 生理年龄引擎

1. 输入：性别、30 天 SDNN/RHR 序列、当日睡眠原始数据（total/in-bed/deep/REM minutes），可配置搜索范围与权重。
2. CSS 计算：`physio_age/css.py` 对时长/效率/恢复性打分，并按 0.40/0.30/0.30 权重合成（默认复用 `backend/utils/sleep_metrics`）。
3. 年龄搜索：遍历 20–80 岁，读取 `hrv_age_table*.csv`，分别计算 `z_sdnn`、`z_rhr`（取反使数值越大越好）、`z_css`，成本函数为 `0.45·z_sdnn² + 0.20·z_rhr² + 0.35·z_css²`。
4. 结果：输出整数生理年龄、软最小化加权年龄、最佳 z-score、使用的数据窗口天数。

### 训练消耗

1. 使用 `libs.training.calculate_consumption` 传入训练组。AU 优先级：显式 AU → RPE×分钟 → 标签兜底（无/低/中/高/极高 → {0,200,350,500,700}）。
2. 曲线：AU ≤150 → 0-5，150-300 → 5-12，300-500 → 12-25，>500 → 25-40（约 900 饱和）；每次训练受 `cap_session` 限制。
3. 当日总消耗受 `cap_training_total` 控制，输出总消耗、剩余准备度（若提供 base）、分项及审计信息。
4. 可通过 `params_override` 调整上限或添加新因子（未来可加入 Journal/设备指标）。

### 基线分析模块

1. `compare_today_vs_baseline`：比较今天与过去 N 天均值（默认 N=7/28/56），输出百分比变化、up/down/flat 旗标，可与 `baseline_overrides` 进行全局基线对比。
2. `compare_recent_vs_previous`：比较近期 N 天平均与更早一段（可映射例如 7 vs 前 28），返回同样的指标信息。
3. 主要用于仪表盘、自动洞察触发或作为 LLM 提示上下文。

### 个性化 CPT 实验

- `tools/personalization_cpt/` 包含历史数据清洗、批量个性化、差异对比等脚本，可生成用户级 emission CPT，产物在 `samples/data/personalization/`。
- 训练后的 CPT 可通过 readiness payload (`emission_cpt_override`) 注入，引擎会使用自定义似然。

### 多服务集成

- `docker-compose.yml` 将 readiness ↔ baseline ↔ physio age 容器互通，便于整体测试。
- `docs/backend/microservices_integration.md` 描述服务发现、消息通道、数据契约。
- `api/main.py` 提供聚合接口示例，可用于内测或 Demo 展示。

</details>
