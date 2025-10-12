<details>
<summary><strong>English</strong></summary>

# Motivue Backend – Service Map

Motivue’s backend is a set of microservices that each tackle a specific piece of
the coaching workflow.  Each top-level service directory (e.g. `readiness/`,
`weekly_report/`, `baseline/`, `physio_age/`, `training/`) can be deployed as a
standalone microservice; they share core Pydantic models (notably
`ReadinessState`) and utilities inside this monorepo, but **execution and data
contracts remain independent**:

- `readiness/` focuses on the daily readiness score (our primary engine).
- `weekly_report/` turns the same readiness data model + history into a Phase 5
  report (Markdown/HTML).  It does not call the readiness engine – both services
  read from / write to the database separately.
- Every service follows the same pattern: **read from database → compute → write
  results back / expose via API**.  Other consumers (front-end, analytics jobs)
  can read the stored JSON/Markdown directly without chaining the services.

## Core services

| Service | What it does | Key modules | Dockerfile |
| --- | --- | --- | --- |
| **Readiness Engine** | Daily readiness score via a Bayesian prior/posterior engine that fuses training load, objective biomarkers, subjective Hooper scores, journals, menstrual cycle and interaction terms.  Exposes a simple REST façade for per-day scoring. | `readiness/service.py`, `readiness/engine.py`, `readiness/mapping.py`, `readiness/constants.py` | `Dockerfile.readiness` |
| **Weekly Report Pipeline** | Multi-agent LLM chain that turns a hydrated `ReadinessState` into chart packs and Markdown/HTML reports (Analyst → Communicator → Critique → Finaliser) with schema validation and fallbacks. | `weekly_report/trend_builder.py`, `weekly_report/pipeline.py`, `weekly_report/finalizer.py`, samples under `samples/weekly_*` | bundled with readiness image (or package separately) |
| **Baseline Service** | Computes and maintains long-term personal baselines (sleep duration/efficiency, restorative ratio, HRV μ/σ) with questionnaire fallbacks and auto-upgrade logic.  Supplies thresholds to the readiness mapper. | `baseline/api.py`, `baseline/service.py`, `baseline/calculator.py`, `baseline/storage.py`, `baseline/auto_upgrade.py` | `Dockerfile.baseline` |
| **Physiological Age** | Estimates physiological age from 30-day HRV/RHR history plus today’s sleep CSS using reference tables per gender. | `physio_age/api.py`, `physio_age/core.py`, `physio_age/css.py`, `physio_age/hrv_age_table*.csv` | `Dockerfile.physio_age` |
| **Training Consumption** | Calculates daily “consumption” points from training sessions (RPE × minutes, AU caps) to display “remaining readiness = readiness − consumption”. | `training/consumption.py`, `training/factors/training.py`, `training/schemas.py` | – |

> Weekly report code now lives under the standalone `weekly_report/` package.  You can deploy it with the readiness image or create a dedicated container if needed.

### Weekly report microservice

- 启动 API：`uvicorn weekly_report.api:app --reload`（依赖 `fastapi` 已包含在 `requirements.txt`）。
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
  - `use_llm=true`：调用 Gemini；通过环境变量 `GOOGLE_API_KEY`、`READINESS_LLM_MODEL`、`READINESS_LLM_FALLBACK_MODELS` 配置模型，留空时自动回退规则。
  - `persist=true`：调用结束后将 Phase 5 结果写入 `weekly_reports` 表（定义在 `api/db.py`，默认使用 `.env` 的 `DATABASE_URL`）。
- 返回值同时包含 Phase 3 `ReadinessState` JSON、Phase 4 `WeeklyReportPackage`、Phase 5 `WeeklyFinalReport`（含 Markdown/HTML/图表 ID）。


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
| `个性化CPT/` | Experiments around personalised emission CPTs (batch scripts, artefacts). | `personalize_cpt.py`, `artifacts/`. |
| `后端文档/` | Additional Chinese documentation (microservice integration, deployment, iOS26 migration, baseline plans). | `MICROSERVICES_INTEGRATION.md`, etc. |

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
- `个性化CPT/` scripts support training and applying customised emission tables; integrate by passing `emission_cpt_override`.

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

### Personalised CPT experiments (`个性化CPT/`)

- Scripts to fit custom emission CPTs from historical labelled data (`personalize_cpt.py`, `train_personalization.py`).
- Supports cleaning history, batch personalisation, comparing deltas.
- Integrate by storing artefacts under `个性化CPT/artifacts` and loading into readiness payloads (override `emission_cpt_override`).

### Multi-service integration

- `docker-compose.yml` links readiness ↔ baseline ↔ physio age, enabling readiness service to call baseline/physio age APIs.
- `后端文档/MICROSERVICES_INTEGRATION.md` details service discovery, MQ topics, and data contracts.
- `API/main.py` offers a simple aggregate service for demos (ingest data, call readiness, store results).

</details>

<details open>
<summary><strong>中文说明</strong></summary>

# Motivue 后端服务总览

Motivue 的后端由多套微服务组成，每个服务解决一个独立的运动科学场景。
各模块在同一个代码库内共享数据模型与工具，但可以独立部署：日常准备度、
周报生成、个性化基线、生理年龄、训练消耗等服务互相解耦。顶层模块映射到
微服务（`readiness/`、`weekly_report/`、`baseline/`、`physio_age/`、`training/`），
它们共用同一套 `ReadinessState` 等 Pydantic 模型，但 **运行流程、接口、落库
策略完全独立**：

- `readiness/` 计算每日准备度，是核心评分引擎；
- `weekly_report/` 仅读取数据库里的准备度/历史数据生成 Phase 5 周报，不调用
  readiness 引擎；
- 任一服务都是“从数据库取数 → 计算 → 把结果（JSON/Markdown 等）写回数据库或通过 API 返回”，
  前端与其他后台只需按需读取存储结果，无需串联多个微服务。

## 核心服务

| 服务 | 功能概述 | 关键模块 | Dockerfile |
| --- | --- | --- | --- |
| **准备度引擎** | 采用贝叶斯先验/后验模型，融合训练负荷、客观生理信号、Hooper 主观评分、Journal 事件、月经周期以及交互项生成每日准备度，并通过 REST 接口对外提供日度评分。 | `readiness/service.py`, `readiness/engine.py`, `readiness/mapping.py`, `readiness/constants.py` | `Dockerfile.readiness` |
| **周报流水线** | 基于多智能体 LLM 的周报生成链路（分析师 → 教练沟通 → 批注 → Finalizer），自动生成图表配置和 Markdown/HTML 报告，内置 Schema 校验与失败回退。 | `weekly_report/trend_builder.py`, `weekly_report/pipeline.py`, `weekly_report/finalizer.py`, `samples/weekly_*` | 可与 readiness 同容器或独立部署 |
| **基线服务** | 计算并维护长期个性化基线（睡眠时长/效率、恢复性、HRV 均值与波动），支持问卷兜底与自动升级，为准备度映射层提供阈值。 | `baseline/api.py`, `baseline/service.py`, `baseline/calculator.py`, `baseline/storage.py`, `baseline/auto_upgrade.py` | `Dockerfile.baseline` |
| **生理年龄服务** | 基于近 30 天 HRV/RHR 历史与当日睡眠 CSS，结合性别参考表估算生理年龄（整数 + 加权小数）。 | `physio_age/api.py`, `physio_age/core.py`, `physio_age/css.py`, `physio_age/hrv_age_table*.csv` | `Dockerfile.physio_age` |
| **训练消耗** | 计算训练“消耗分”，用于显示“剩余准备度 = 准备度 − 当日消耗”，不影响准备度后验。 | `training/consumption.py`, `training/factors/training.py`, `training/schemas.py` | – |

> 周报代码已迁移到独立的 `weekly_report/` 包，可单独构建镜像或与 readiness 共用部署。

## 目录速览

| 路径 | 作用 | 重点文件 |
| --- | --- | --- |
| `api/` | 旧版 FastAPI 聚合层（用于内部 Demo）。 | `api/main.py`。 |
| `backend/` | 通用工具，目前主要提供睡眠指标计算。 | `backend/utils/sleep_metrics.py`：计算睡眠效率与恢复性。 |
| `baseline/` | 个体基线服务，含接口、算法、存储与部署文档。 | `baseline/README.md`、`baseline/API_REFERENCE.md`。 |
| `baseline_analytics/` | 独立的窗口对比工具（今日 vs 基线、近期 vs 往期）。 | `compare_today_vs_baseline`、`compare_recent_vs_previous`。 |
| `docs/` | 设计方案与集成笔记（如周报后端说明、提示词规划等）。 | `weekly_report_backend_notes.md`、各类 PDF。 |
| `gui/` | 原型界面与演示资源。 | – |
| `physio_age/` | 生理年龄引擎（见上）。 | 示例脚本与参考表。 |
| `readiness/` | 准备度核心模块、规则洞察、映射与 Hooper/ACWR 工具。 | `state.py`、`insights/rules.py`、`metrics_extractors.py`。 |
| `weekly_report/` | 周报服务（趋势图、工作流、多智能体、Finalizer）。 | `weekly_report/models.py`、`weekly_report/trend_builder.py`、`weekly_report/pipeline.py`、`weekly_report/workflow/graph.py`、`weekly_report/finalizer.py`。 |
| `samples/` | 回归样例与输出结果。 | `weekly_report_sample.json`、`weekly_report_final_sample.md`、`readiness_state_report_sample.json`。 |
| `scripts/` | 运维脚本。 | `scripts/db_check.py`。 |
| `training/` | 训练消耗计算模块。 | `training/README.md` + 因子实现。 |
| `tmp/` | 临时文件目录。 | – |
| `个性化CPT/` | 证据 CPT 个性化实验脚本与成果。 | `personalize_cpt.py`、`artifacts/`。 |
| `后端文档/` | 中文文档合集（微服务集成、部署、iOS26 迁移、基线计划等）。 | `MICROSERVICES_INTEGRATION.md` 等。 |
| `docs/weekly_report_frontend_notes.md` | 周报前端对接说明（接口、字段、渲染提示）。 | – |

## 关键文档与样例

- `docs/weekly_report_backend_notes.md`：周报 Phase 4/5 后端集成指南。  
- `readiness_state_plan.txt`：五阶段准备度规划。  
- `samples/weekly_report_final_sample.*`：Finalizer 生成的 Markdown/JSON。  
- `AI_prompt_doc.txt`、`S&C周报LLM流程优化.pdf`、`运动科学数据洞察生成.pdf`：提示词与研究资料。

## 服务运行方式

```bash
# 构建核心服务镜像
docker build -f Dockerfile.readiness -t motivue-readiness .
docker build -f Dockerfile.baseline   -t motivue-baseline .
docker build -f Dockerfile.physio_age -t motivue-physio-age .

# 示例脚本
python readiness/examples/simulate_days_via_service.py
python physio_age/examples/series_usage.py
python samples/generate_weekly_report_samples.py
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

#### 先验计算（详见 `readiness/engine.py`）
1. **状态转移**：`BASELINE_TRANSITION_CPT` 计算昨日→今日的基础概率。
2. **训练负荷**：`TRAINING_LOAD_CPT` × `CAUSAL_FACTOR_WEIGHTS['training_load']` 调整先验。
3. **连续高强惩罚**：最近 4/8 天高强度次数触发概率向 `NFOR` 偏移（0.5 或 0.6）。
4. **ACWR 与短期疲劳**：
   - 计算 AU 滑窗均值（A7、C28、A3）。
   - R7/28 ≤0.9 → 奖励（向 `Peak`/`Well-adapted` 转移）。
   - R7/28 ≥1.15 → 惩罚（向 `Acute Fatigue`/`NFOR` 转移），严重度与慢性负荷、R3/28 相关。
   - DOMS + Energy 与 AU 归一指标构成疲劳得分，控制 `Acute Fatigue`。
5. **昨天 Journal**：酒精、晚咖、屏幕、晚餐使用对应 CPT 乘权；生病/受伤继承到今日的 evidence pool，但不影响先验。

#### 后验更新
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
- **个人化 CPT**：可通过 payload 的 `emission_cpt_override` 注入，或使用 `个性化CPT/` 工具训练产生。

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

1. 使用 `training.calculate_consumption` 传入训练组。AU 优先级：显式 AU → RPE×分钟 → 标签兜底（无/低/中/高/极高 → {0,200,350,500,700}）。
2. 曲线：AU ≤150 → 0-5，150-300 → 5-12，300-500 → 12-25，>500 → 25-40（约 900 饱和）；每次训练受 `cap_session` 限制。
3. 当日总消耗受 `cap_training_total` 控制，输出总消耗、剩余准备度（若提供 base）、分项及审计信息。
4. 可通过 `params_override` 调整上限或添加新因子（未来可加入 Journal/设备指标）。

### 基线分析模块

1. `compare_today_vs_baseline`：比较今天与过去 N 天均值（默认 N=7/28/56），输出百分比变化、up/down/flat 旗标，可与 `baseline_overrides` 进行全局基线对比。
2. `compare_recent_vs_previous`：比较近期 N 天平均与更早一段（可映射例如 7 vs 前 28），返回同样的指标信息。
3. 主要用于仪表盘、自动洞察触发或作为 LLM 提示上下文。

### 个性化 CPT 实验

- `个性化CPT/` 包含历史数据清洗、批量个性化、差异对比等脚本，可生成用户级 emission CPT。
- 训练后的 CPT 可通过 readiness payload (`emission_cpt_override`) 注入，引擎会使用自定义似然。

### 多服务集成

- `docker-compose.yml` 将 readiness ↔ baseline ↔ physio age 容器互通，便于整体测试。
- `后端文档/MICROSERVICES_INTEGRATION.md` 描述服务发现、消息通道、数据契约。
- `api/main.py` 提供聚合接口示例，可用于内测或 Demo 展示。

</details>
