# Readiness（就绪度）模块

一个自包含的贝叶斯就绪度计算引擎与工具集。引擎清晰地分离“先验”（昨日→今日的状态转移 + 训练负荷与小幅调节）与“后验”（将今天的主观与客观证据按条件概率融合），既满足直觉化业务规则，也便于未来扩展更多证据与个性化。

> **最近更新（2025-10）**
> - Phase 3A 接入 Gemini LLM（多假设推理 + 自我批判），在默认流程失败时自动回退 mock。
> - `RawInputs` 新增可选 `report_notes` 自由文本，可由周报/LLM 读取；不影响原有日度计算。
> - Phase 3 规则扩展：增加 HRV×神经肌肉双疲劳、睡眠×生活方式联动、主观优先预警、生活方式趋势叠加、主客观冲突检测等逻辑。
> - Phase 4 周报骨架到位：趋势图封装、Analyst/Communicator/Critique LLM 管线与示例脚本。
> - Phase 5 调整为“Finalizer”方案（将结构化结果转为最终 Markdown/HTML），原通知/跟进/反馈流程保留为未来扩展。

----------------------------------------
## 阶段进展速览
- **Phase 1（数据摄入）**：`ReadinessState` ingest + metrics 计算；payload 与数据库字段一一对应，新增 `report_notes` 供周报使用。
- **Phase 2（确定性指标）**：`metrics_extractors` 计算训练/睡眠/HRV/主观指标；所有写入都通过 Pydantic 校验。
- **Phase 3（规则洞察）**：`insights/rules.py` 输出结构化 `InsightItem`，并扩展了五条生活方式/冲突检测规则。
- **Phase 3A（ToT & Critique）**：复杂度判定后调用 Gemini 生成多假设 + 自我批判，结果写入 `state.insight_reviews`。
- **Phase 4（周报骨架）**：
  - `readiness/report/models.py`：定义周报 Schema（`ChartSpec`, `WeeklyHistoryEntry`, `AnalystReport`, `CommunicatorReport`, `ReportCritique`, `WeeklyReportPackage` 等）。
  - `readiness/report/trend_builder.py`：聚合历史数据 → 生成准备度/HRV/睡眠/训练/Hooper/生活方式图表（解耦，可单独调用），并支持准备度 × HRV 组合视图。
  - `readiness/report/pipeline.py`：调用 Gemini（fallback 兜底）产出 Analyst/Communicator/Critique，最终形成结构化周报对象。
  - 示例脚本 `samples/generate_weekly_report_samples.py` 写出 `samples/weekly_report_sample.json`（含自然语言段落 + 推荐图表）。
  - **其余 readiness 目录文件**（例如 `service.py`, `engine.py`, `metrics_extractors.py`, `insights/`, `workflow/graph.py` 等）仍用于日常准备度计算，与周报模块解耦。
- **Phase 5（Finalizer）**：`readiness/report/finalizer.generate_weekly_final_report` 将 Phase 4 JSON + 准备度历史/训练笔记整合为 Markdown/HTML 成品（支持 Gemini 或 fallback 模板），示例脚本输出 `samples/weekly_report_final_sample.*`；原“通知/跟进/反馈”方案保留为未来扩展。

- **Phase 1（数据摄入）**：`ReadinessState` ingest + metrics 计算；payload 与数据库字段一一对应，新增 `report_notes` 供周报使用。
- **Phase 2（确定性指标）**：`metrics_extractors` 计算训练/睡眠/HRV/主观指标；所有写入都通过 Pydantic 校验。
- **Phase 3（规则洞察）**：`insights/rules.py` 输出结构化 `InsightItem`，并扩展了五条生活方式/冲突检测规则。
- **Phase 3A（ToT & Critique）**：复杂度判定后调用 Gemini 生成多假设 + 自我批判，结果写入 `state.insight_reviews`。
- **Phase 4（周报骨架）**：
  - `readiness/report/trend_builder.py` 生成 HRV/睡眠/训练/Hooper/生活方式图表（解耦，可单独调用）。
  - `readiness/report/pipeline.generate_weekly_report` 调用 LLM（fallback 兜底）产出 Analyst/Communicator/Critique + ChartSpec。
  - 示例脚本 `samples/generate_weekly_report_samples.py` 输出 `weekly_report_sample.json`（含自然语言段落 + 图表数据）。
- **Phase 5（Finalizer）**：`readiness/report/finalizer.generate_weekly_final_report` 将 Phase 4 JSON + 准备度历史/训练笔记整合为 Markdown/HTML 成品（支持 Gemini 或 fallback 模板），示例脚本输出 `samples/weekly_report_final_sample.*`；原“通知/跟进/反馈”方案保留为后续可扩展模块。

----------------------------------------
## 总览与典型来源
- 穿戴/平台（自动采集）
  - Apple Watch/HealthKit：睡眠时长与效率（sleep_performance）、深睡/REM 比例（restorative_sleep）、HRV RMSSD 趋势（hrv_trend）。
  - 其他平台数据可在后端转译为上述枚举。
- App 手动输入（低摩擦）
  - 训练强度：默认仅“标签”（无/低/中/高/极高）；可开启进阶开关填 RPE(1–10) 与时长(分钟)，由后端换算 AU（任意单位）。
  - Hooper 主观（1..7）：疲劳/酸痛/压力/睡眠。
  - Journal 事件：喝酒/晚咖/睡前屏幕/晚餐/生病/受伤/…（支持上百种与自定义）。
  - 女性周期：cycle day/length。

说明：若提供 AU 序列（近 28 天），引擎优先使用 AU 并启用 ACWR 小幅调节（当 AU ≥7 天时）。否则回退到“训练强度标签”。

----------------------------------------
## 快速开始（本地调用）
`python
from readiness.service import compute_readiness_from_payload
import json

payload = json.loads(open('readiness/examples/male_request.json', 'r', encoding='utf-8').read())
res = compute_readiness_from_payload(payload)
print(res['final_readiness_score'], res['final_diagnosis'])
`

----------------------------------------
## 端到端数据流（前端 → 后端 → 引擎）
1) 前端采集（最少）：
   - 默认：训练强度标签（无/低/中/高/极高）。
   - 进阶开关（可选）：RPE(1–10) 与时长(分钟)。
   - 可选：Hooper(1..7)、睡眠/HRV 枚举、Journal 事件、女性周期。
2) 后端持久化（建议字段）：
   - training_label: string（无/低/中/高/极高，作为回退输入）
   - rpe_0_10: number；duration_min: number（两者同时有时计算 AU）
   - daily_au: number（= RPE × 时长，由后端计算）
   - 日级滚动保存，方便聚合出近 28 天 AU 列表。
3) 服务/API 调用（与引擎对接）：
   - 优先传 recent_training_au: number[]（近 28 天日 AU）
   - 无 AU 时回退 recent_training_loads: string[]（无/低/中/高/极高）
   - 其他证据按需传入（见“API 请求字段”）。
4) 引擎计算：
   - 先验：基线转移 + 训练负荷 CPT + 连天高强惩罚 + 小幅 ACWR 调节（慢性保护）+ 昨日日志短期影响。
   - 后验：Hooper/睡眠/HRV 等条件概率表融合，女性周期（可选）以连续似然参与。
5) 返回结果：
   - 分数（0..100）、诊断状态、先验/后验分布、更新历史、下一日 previous_state_probs。

----------------------------------------
## API 契约（payload = 请求体 JSON）
- 基本：
  - user_id: string；date: YYYY-MM-DD；gender: string（“男”/“女”）
  - previous_state_probs: object（状态名→概率，六键：Peak/Well-adapted/FOR/Acute Fatigue/NFOR/OTS；首日可用默认 {Peak:0.1, Well-adapted:0.5, FOR:0.3, Acute Fatigue:0.1, NFOR:0, OTS:0}）
- 训练负荷（2 选 1，优先 AU）：
  - recent_training_au?: number[]（近 28 天日 AU；历史 <7 天不启用 ACWR）
  - recent_training_loads?: string[]（回退；无/低/中/高/极高；亦用于“连续训练惩罚”）
  - training_load?: string（当天标签，供细化用）
- Journal（昨天，统一 JSON）：
  - 短期（仅影响今天先验，用后自动清除）：alcohol_consumed，late_caffeine，screen_before_bed，late_meal，以及其它自定义键（默认只记录与清除，不参与计算，除非加入白名单）。
  - 持续（仅影响今天后验，直到显式取消）：is_sick，is_injured。
- 后验证据（今天）：
  - objective: { sleep_performance_state ∈ {good,medium,poor}, restorative_sleep ∈ {high,medium,low}, hrv_trend ∈ {rising,stable,slight_decline,significant_decline} }
  - hooper: { fatigue, soreness, stress, sleep }（1..7）
  - cycle?: { day, cycle_length }（女性，可选）
  - report_notes?: string（周报/LLM 使用的自由文本，可为空）
- Response（JSON）：
  - prior_probs；final_posterior_probs；final_readiness_score；final_diagnosis
  - evidence_pool；update_history；next_previous_state_probs（供次日 previous_state_probs 使用）
- 行为说明（服务内部）：
  - 先验（今天）= previous_state_probs × 基线转移 × training_load（昨天）× journal（昨天短期项）× 小幅 ACWR 调节（当 AU 历史≥7 天）。
  - 后验（今天）= 先验 × objective（今天）× hooper（今天）× cycle（今天）× journal（昨天持续项若仍有效）。

**示例（请求 JSON）**：
`json
{
  "user_id": "u001",
  "date": "2025-09-05",
  "previous_state_probs": {"Peak":0.1, "Well-adapted":0.5, "FOR":0.3, "Acute Fatigue":0.1, "NFOR":0.0, "OTS":0.0},
  "training_load": "高",
  "recent_training_loads": ["高","高","中","高","高","极高","中","高"],
  "journal": {"alcohol_consumed": true, "is_sick": false},
  "objective": {"sleep_performance_state":"medium", "hrv_trend":"stable"},
  "hooper": {"fatigue":3, "soreness":3, "stress":3, "sleep":3},
  "cycle": null
}
`

----------------------------------------
## Journal 政策（自定义/清除/计算白名单）
- Journal 支持上百种键，并允许自定义扩展。
- 持续项：仅 is_sick、is_injured —— 进入当天后验，持续生效，直到某天在 journal 中取消（设为 false）。
- 短期项：其余一律按短期处理 —— 仅影响一次（作为昨天→今天的先验），在“用于昨天的存储”中自动清除；但原始记录都保存在 user_daily.journal 里，供回顾分析。
- 计算白名单（默认）：
  - 先验（短期）：alcohol_consumed，late_caffeine，screen_before_bed，late_meal
  - 后验（持续）：is_sick，is_injured
- 其它短期键（如 high_stress_event_today，meditation_done_today）默认仅记录与清除，不参与计算；如需参与，后续可加入白名单或为其增加 CPT/似然映射。

----------------------------------------
## 引擎运行逻辑（自然语言）
1) 先验（Prior）
- 基线转移：依上一日状态分布与状态转移表。
- 训练负荷：按“当天标签”与“近期标签/或 AU 序列”修正，包含“连续高强”惩罚（最近 4/8 天高强度阈值）。
- ACWR 小幅调节（A7/C28，以慢性保护为主）：
  - 稳态（0.9–1.1）不动；
  - 急性高 + 慢性低 → 轻惩罚（-1..-2 分）；
  - 急性高 + 慢性高 → 慢性保护（惩罚减半或接近不动）；
  - 急性低（≤0.9）→ 小奖励（≈+1 分）；
  - 极低急性 + 慢性低 → 极轻微去适应（<1 分）；
  - 保险：recent_training_au 少于 7 天不启用 ACWR。
- 昨日短期 Journal：酒精/晚咖/睡前屏幕/晚餐影响今日先验；今日持久状态（生病/受伤）在后验生效。
2) 后验（Posterior）
- Hooper（1..7）与睡眠/HRV 等证据按 CPT 融合；女性周期（如提供）以连续似然参与。
- 权重配置集中在 constants.py（本次未改权重）。
3) 输出
- 返回当日分数/诊断，并提供下一日 previous_state_probs 以便链式运行。

----------------------------------------
## 数据库设计（建议）
- 表 user_daily（按日一行）
  - user_id (PK part)，date (PK part)
  - previous_state_probs JSON（存昨天后验，供次日作为 previous_state_probs）
  - training_load VARCHAR（昨天训练强度标签，供次日先验）
  - journal JSON（当天整份原始 journal；次日作为“昨天 journal”传计算）
  - objective JSON（sleep_performance_state/restorative_sleep/hrv_trend）
  - hooper JSON（fatigue/soreness/stress/sleep）
  - cycle JSON（女性，可空）
  - final_readiness_score INT，final_diagnosis VARCHAR
  - final_posterior_probs JSON，next_previous_state_probs JSON
  - 可选：daily_au NUMBER，training_label VARCHAR（作为聚合 AU 与回退输入）
- 约束与校验
  - (user_id, date) 唯一；Hooper 值域 1..7；objective/cycle/journal 枚举值校验。
- 个性化（可选）
  - 表 user_models：user_id，model_type='EMISSION_CPT'，payload_json，version，created_at。

----------------------------------------
## 代码模块
- readiness/service.py：统一入口 compute_readiness_from_payload；拆分“昨天/今天”的 journal 写入与分类；聚合先验/后验输入。
- readiness/engine.py：先验/后验编排，含 ACWR 调节、连续高强惩罚、短期清除、证据融合、周期连续似然；JournalManager 为内存实现。
- readiness/mapping.py：原始值→枚举（睡眠/HRV/Hooper）。
- readiness/hooper.py：Hooper 映射（分档 + 同档内层次）。
- readiness/constants.py：CPT、证据权重、冷启动“标签→AU”映射（无0/低200/中350/高500/极高700）。
- readiness/examples：请求样例（AU 形态）与回归数据。

----------------------------------------
## 例子
- 请求样例（AU 形态）：readiness/examples/male_request.json、readiness/examples/female_request.json
- 批量模拟：readiness/simulate_days_via_service.py 生成 10/30 天数据
- 一次调用：见“快速开始”代码片段

----------------------------------------
## 术语与说明
- payload：指计算服务的请求体 JSON（POST /readiness 的 body），或传给 readiness.service.compute_readiness_from_payload 的字典。
- AU：由 RPE(1–10) × 时长(分钟) 得到的“训练任意单位”（用户不需要看到 AU，前端只填 RPE/时长或训练标签）。

----------------------------------------
## 功能总览与文件映射
- **Readiness API 与引擎**：`api/main.py`, `readiness/service.py`, `readiness/engine.py`, `readiness/mapping.py`, `readiness/constants.py`  
  - FastAPI 接口聚合 HealthKit 数据、调用引擎、持久化结果，并负责训练消耗接口与个性化 CPT 缓存。
  - 引擎执行日先验/后验更新、ACWR 调整、Hooper 权重和月经周期证据，支持按用户覆盖 EMISSION_CPT。
  - Mapping 层将原始数值映射为模型枚举，处理 iOS26 睡眠评分与传统睡眠指标的“二选一”逻辑。
- **Phase 3A LLM 扩展**：`readiness/llm/models.py`, `readiness/llm/provider.py`, `readiness/workflow/graph.py`  
  - 复杂度判断后调用 Gemini JSON Mode 生成多假设推理与自我批判，失败时回退 mock。
  - 新增 `report_notes` 会被透传给 LLM，方便周报或教练语境使用。
- **Weekly Report Pipeline**：`readiness/report/models.py`, `readiness/report/trend_builder.py`, `readiness/report/pipeline.py`  
  - 根据历史数据生成 HRV/睡眠/训练等图表，并通过 Analyst/Communicator/Critique LLM 节点自动生成周报草稿（若 LLM 不可用则使用 heuristic fallback）。

- **Baseline 服务**：`baseline/api.py`, `baseline/service.py`, `baseline/calculator.py`, `baseline/storage.py`, `baseline/default_baselines.py`, `baseline/auto_upgrade.py`, `baseline/updater.py`, `baseline/healthkit_integration.py`  
  - 负责睡眠/HRV 基线计算、验证与存储，支持 7 天增量、30 天重算、自动升级与 MQ 通知。
  - HealthKit 集成模块解析 XML/API 数据为结构化 `SleepRecord`、`HRVRecord`。

- **Baseline Analytics**：`baseline_analytics/daily_vs_baseline.py`, `baseline_analytics/periodic_review.py`, `baseline_analytics/utils.py`  
  - 提供纯函数对比“今天 vs 基线”“最近 N vs 上一个 N”，供前端和报告直接调用。

- **训练消耗与 Physio Age**：`training/consumption.py`, `training/factors/training.py`, `training/schemas.py`, `physio_age/core.py`, `physio_age/api.py`, `physio_age/css.py`  
  - 训练模块按 RPE×分钟或负荷标签计算当天 readiness 消耗并回写剩余分。
  - Physio Age 服务基于 30 天 HRV/RHR 序列与当天 CSS 计算生理年龄，并复用睡眠指标计算逻辑。

- **个性化 CPT 工具链**：`个性化CPT/train_personalization.py`, `个性化CPT/personalize_cpt.py`, `个性化CPT/monthly_update.py`, `个性化CPT/clean_history.py`, `个性化CPT/README.md`  
  - 提供 EM 式离线训练，把日级历史 CSV 转换为用户定制 EMISSION_CPT，可通过 MQ 热加载到 `UserModel`。

- **通用工具与脚本**：`backend/utils/sleep_metrics.py`, `scripts/db_check.py`, `gui/app.py`  
  - 睡眠工具输出效率/恢复性供多服务复用；脚本校验数据库连通性；Streamlit GUI 支持手动录入和 CSV 导出。

- **数据库模型**：`api/db.py`  
  - 定义 readiness 日表、个性化模型、基线缓存结构，并提供统一 `Session` 工厂。

- **Docker 与部署文档**：`Dockerfile.*`, `docker-compose.yml`, `BASELINE_DEPLOYMENT_CHECKLIST.md`, `后端文档/*.md`  
  - 提供 Readiness/Baseline/Physio Age 容器及部署、迁移与运维指引。
