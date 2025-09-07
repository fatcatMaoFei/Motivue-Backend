# Readiness（就绪度）引擎

自包含的贝叶斯就绪度引擎与示例。支持“训练强度标签”或“RPE×时长→AU”的输入，内置小幅 ACWR 调节（以慢性保护为主），并与主观 Hooper/睡眠/HRV 等证据融合。

## 快速开始
- Python 3.11+

示例（读取示例 JSON 直接计算）
`python
from readiness.service import compute_readiness_from_payload
import json

payload = json.loads(open('readiness/examples/male_request.json', 'r', encoding='utf-8').read())
res = compute_readiness_from_payload(payload)
print(res['final_readiness_score'], res['final_diagnosis'])
`

## 前端/后端对接（新增）
- 前端
  - 默认：单选“训练强度标签”＝ 无/低/中/高/极高
  - 进阶（可选开关）：RPE(1–10) 与 时长(分钟)。前端不暴露 AU 概念
- 后端/数据库
  - 保存：pe_0_10、duration_min、daily_au（=RPE×时长）与 	raining_label
  - 聚合近 28 天 daily_au 作为 AU 序列；若缺 AU，则回退到标签序列
- 服务 API（兼容旧版）
  - 优先键：ecent_training_au: number[]（近 28 天 AU）
  - 回退键：ecent_training_loads: string[]（无/低/中/高/极高）。服务内置默认映射：无0/低200/中350/高500/极高700

## 引擎运行逻辑（简述）
- 先验（Prior）
  - 昨日→今日的基线转移
  - 训练负荷先验（标签或 AU）+ 连天高强惩罚
  - ACWR 小幅调节（A7/C28，默认幅度≈1–2 分；极端≤3 分）
    - 稳态（0.9–1.1）：不动
    - 急性高 + 慢性低：轻惩罚；急性高 + 慢性高：保护减半
    - 急性低（≤0.9）：小奖励；极低急性且慢性低：极轻微去适应
    - 保险：少于 7 天历史时不启用 ACWR（中性）
  - 日志（昨日短期：酒精/晚咖/睡前屏幕/晚餐）对今日先验的细调
- 后验（Posterior）
  - Hooper 主观（疲劳/酸痛/压力/睡眠，1..7）、睡眠表现（good/medium/poor）、恢复性睡眠（high/medium/low）、HRV 趋势（rising/stable/slight_decline/significant_decline）等证据按 CPT 累乘
  - 月经周期（可选）以连续似然参与
  - 读数权重在 constants 中配置；本次改动未调整权重

## 主要模块
- eadiness/service.py：统一入口 compute_readiness_from_payload（接受上述键，返回分数/诊断/先验/后验）
- eadiness/engine.py：先验/后验编排，含 ACWR 调节与日志处理
- eadiness/mapping.py：原始输入→模型变量映射
- eadiness/hooper.py：Hooper 分数映射（分档+同档内层次）
- eadiness/constants.py：CPT、证据权重、默认映射（含标签→AU）

## 示例
- 请求样例（已对齐 AU 形态）
  - eadiness/examples/male_request.json
  - eadiness/examples/female_request.json
- 输出/历史示例
  - eadiness/examples/sim_user*_*.csv/.jsonl

## 注意
- 新用户无历史也可运行：不足 7 天则不启用 ACWR，逻辑保持中性
- 建议后端尽早累积 daily_au，以便触发“慢性保护”
# Readiness（就绪度）模块

一个自包含的贝叶斯就绪度计算引擎及其辅助工具。从旧版动态模型抽取并整理为独立包，便于调用与维护。引擎将“先验”（昨日→今日的状态转移 + 训练负荷与小幅调节）与“后验”（主观与客观证据的条件概率融合）分离，既保证直觉化的业务规则，又能逐步扩展更丰富的数据证据。

典型使用场景（数据来源举例）：
- 穿戴与平台（自动采集）
  - Apple Watch/HealthKit：睡眠时长与效率（映射为 sleep_performance）、深睡/REM 比例（restorative_sleep）、HRV RMSSD（hrv_trend）。
  - 其他平台的等价数据也可通过后端转译为上述枚举。
- App 手动输入（低摩擦）
  - 训练强度标签（无/低/中/高/极高），或打开“进阶开关”输入 RPE(1–10) 与时长(分钟)，后端据此计算 AU（训练任意单位）。
  - Hooper 主观评分（疲劳/酸痛/压力/睡眠，1..7）。
  - 简化 Journal 事件（日常：酒精/晚咖啡/睡前屏幕/晚餐；持久：生病/受伤/重大压力/冥想）。
  - 月经周期（女性用户，可选）：cycle day 与周期长度。

引擎的“训练负荷”支持两种输入路径：
- 简单模式：仅标签（无/低/中/高/极高）。
- 进阶模式：RPE×时长（由后端换算为 AU 并累积 28 天）。
不展示 AU 给用户；如提供 AU 列表，则优先使用 AU（否则用标签自动映射）。

---

## 快速开始
- Python 3.11+

示例（读取示例 JSON 直接计算）：
```python
from readiness.service import compute_readiness_from_payload
import json

payload = json.loads(open('readiness/examples/male_request.json', 'r', encoding='utf-8').read())
res = compute_readiness_from_payload(payload)
print(res['final_readiness_score'], res['final_diagnosis'])
```

---

## 全局架构与数据流（前端 → 后端 → 引擎）
1) 前端采集（最少）
   - 默认：训练强度标签（无/低/中/高/极高）。
   - 进阶开关（可选）：RPE(1–10) 与时长(分钟)。
   - 可选：Hooper(1..7)、睡眠/HRV 枚举、Journal 事件、月经周期。

2) 后端持久化（建议字段）
   - `training_label: string`（无/低/中/高/极高，作为回退输入）
   - `rpe_0_10: number`，`duration_min: number`（两者都有时计算）
   - `daily_au: number`（= RPE × 时长，由后端计算）
   - 日级滚动保存，便于聚合出近 28 天 AU 列表。

3) 服务/API 调用（与引擎对接）
   - 优先传 `recent_training_au: number[]`（近 28 天日 AU）
   - 无 AU 时回退传 `recent_training_loads: string[]`（无/低/中/高/极高）
   - 其他证据字段按需传入（见“API 请求字段”）。

4) 引擎计算
   - 先验：基线转移 + 训练负荷 CPT + 连天高强惩罚 + 小幅 ACWR 调节（以慢性保护为主）+ 昨日日志短期影响。
   - 后验：Hooper/睡眠/HRV 等条件概率表融合，月经周期（可选）以连续似然参与。

5) 返回结果
   - 分数（0..100）、诊断状态、先验/后验分布、更新历史、下一日 previous_state_probs。

---

## API 请求字段（前端→后端→服务）
- 基本：
  - `user_id: str`，`date: YYYY-MM-DD`，`gender: str`（“男”/“女”）
  - `previous_state_probs?: Dict[state, prob]`（可选，链式运行时传上一日后验）

- 训练负荷（2 选 1，优先 AU）：
  - `recent_training_au?: number[]`（近 28 天日 AU，RPE×时长由后端计算）
  - `recent_training_loads?: string[]`（回退；无/低/中/高/极高）
  - `training_load?: string`（当天标签，可用于日志中“晚餐影响方向”等细化）

- Journal（JSON）：
  - 短期（昨晚影响今日先验）：`alcohol_consumed`，`late_caffeine`，`screen_before_bed`，`late_meal`
  - 持久（今日影响今日后验）：`is_sick`，`is_injured`，`high_stress_event_today`，`meditation_done_today`

- 后验证据（客观与主观）：
  - 眠：`sleep_performance_state ∈ {good, medium, poor}`
  - 恢复性睡眠：`restorative_sleep ∈ {high, medium, low}`
  - HRV 趋势：`hrv_trend ∈ {rising, stable, slight_decline, significant_decline}`
  - Hooper：`hooper: {fatigue, soreness, stress, sleep}（1..7）`
  - 月经周期（可选）：`cycle: {day: int, cycle_length: int}`

- 返回：
  - `final_readiness_score: int`，`final_diagnosis: str`
  - `prior_probs`，`final_posterior_probs`
  - `evidence_pool`，`update_history`，`next_previous_state_probs`

---

## 引擎运行逻辑（自然语言）
1) 先验（Prior）
   - 基线转移：依据上一日状态分布与状态转移表。
   - 训练负荷：按“当天标签”与“近期标签/或 AU 序列”进行先验修正，包含“连续高强”的惩罚。
   - ACWR 小幅调节（A7/C28）：
     - 稳态（0.9–1.1）最安全，不动；
     - 急性高 + 慢性低 → 轻惩罚（-1..-2 分）；
     - 急性高 + 慢性高 → 慢性保护（惩罚减半或接近不动）；
     - 急性低（≤0.9）→ 小奖励（≈+1 分）；
     - 极低急性 + 慢性低 → 极轻微去适应（<1 分）。
     - 保险：`recent_training_au` 少于 7 天时不启用 ACWR（中性）。
   - 日志（昨日短期）：酒精/晚咖啡/睡前屏幕/晚餐，影响今日先验；今日持久状态（生病/受伤/压力/冥想）不进先验，在后验阶段生效。

2) 后验（Posterior）
   - Hooper（1..7）与睡眠/HRV 等证据按 CPT 融合，月经周期（如提供）以连续似然参与。
   - 证据权重统一配置于 `constants.py`，本次改动未调整权重。

3) 结果
   - 返回当日分数与诊断，并提供下一日 `previous_state_probs` 以便链式调用。

---

## 文件/模块说明

- `readiness/service.py`
  - 对外统一入口：`compute_readiness_from_payload(payload: dict) -> dict`
  - 负责将请求拼装为引擎的先验/后验输入，并对 Journal 做“昨晚/今晨”写入的区分。

- `readiness/engine.py`
  - 先验/后验的核心编排：基线、训练负荷、ACWR 调节、日志、证据融合、月经周期。
  - `JournalManager`（内存）：简单、可替换的数据落库抽象。

- `readiness/mapping.py`
  - 原始值→枚举：睡眠表现、恢复性睡眠、HRV 趋势；Hooper（含连续/分档映射）。

- `readiness/hooper.py`
  - Hooper 映射：分档（1–2 低、3–5 中、6–7 高）且同档内有层次，避免“同分档无差异”。

- `readiness/constants.py`
  - CPT 表与权重；冷启动“标签→AU”映射：无0/低200/中350/高500/极高700。

- 其他工具
  - `readiness/gui_daily_sim.py`：本地 GUI，用于手工输入与逐日模拟（可选）。
  - `readiness/simulate_days_via_service.py`：批量生成 10/30 天数据用于回归验证。
  - `readiness/exp_*`：实验/敏感性脚本（例如 Hooper/ACWR 测试）。

- 示例数据
  - 请求：`readiness/examples/male_request.json`，`readiness/examples/female_request.json`（AU 形态）
  - 结果：`readiness/examples/sim_user*_*.csv/.jsonl`

---

## 使用范式（典型流程）
```python
from readiness.service import compute_readiness_from_payload

payload = {
  "user_id": "u1",
  "date": "2025-09-06",
  # 训练负荷（推荐 AU；无 AU 时传标签 recent_training_loads）
  "recent_training_au": [350]*21 + [500]*7,
  # Hooper 与客观证据（可选）
  "hooper": {"fatigue":3, "soreness":3, "stress":3, "sleep":3},
  "objective": {"sleep_performance_state":"medium", "restorative_sleep":"medium", "hrv_trend":"stable"},
  # Journal（短期：昨晚；持久：今日）
  "journal": {"alcohol_consumed":false, "late_caffeine":false, "screen_before_bed":false, "late_meal":false,
               "is_sick":false, "is_injured":false}
}

res = compute_readiness_from_payload(payload)
print(res['final_readiness_score'], res['final_diagnosis'])
```

---

## 注意事项
- 新用户无历史也可运行：`recent_training_au` < 7 天时不启用 ACWR，逻辑保持中性。
- 建议后端尽早累积 `daily_au`，以便触发“慢性保护”。
- 连续运行多天：将 `next_previous_state_probs` 作为下一日 `previous_state_probs` 链式调用。
- Journal：短期行为写入“昨天”、影响今日先验；持久状态写入“今天”、影响今日后验。
# Readiness（就绪度）模块

一个自包含的贝叶斯就绪度计算引擎及其辅助工具。从旧版动态模型抽取并整理为独立包，便于调用与维护。引擎将“先验”（昨日→今日的状态转移 + 训练负荷与小幅调节）与“后验”（主观与客观证据的条件概率融合）解耦，既支持直觉化业务规则，又能逐步扩展更丰富的数据证据。

典型数据来源（示例）：
- 穿戴与平台（自动）：
  - Apple Watch/HealthKit：睡眠时长与效率（映射为 sleep_performance）、深睡/REM 比例（restorative_sleep）、HRV RMSSD（hrv_trend）。
  - 其他平台的等价数据可在后端转译为上述枚举。
- App 手动（低摩擦）：
  - 训练强度标签（无/低/中/高/极高），或开启“进阶开关”输入 RPE(1–10) 与时长(分钟)，由后端换算 AU（训练任意单位）。
  - Hooper 主观（疲劳/酸痛/压力/睡眠，1..7）。
  - 简化 Journal（喝酒/晚咖/睡前屏幕/晚餐/生病/受伤…；亦支持自定义键，见 Journal 政策）。
  - 女性周期（cycle day/length）。

---

## 快速开始
- Python 3.11+

示例（读取示例 JSON 直接计算）：
```python
from readiness.service import compute_readiness_from_payload
import json

payload = json.loads(open('readiness/examples/male_request.json', 'r', encoding='utf-8').read())
res = compute_readiness_from_payload(payload)
print(res['final_readiness_score'], res['final_diagnosis'])
```

---

## 全局架构与数据流（前端 → 后端 → 引擎）
1) 前端采集（最少）
   - 默认：训练强度标签（无/低/中/高/极高）。
   - 进阶开关（可选）：RPE(1–10) 与时长(分钟)。
   - 可选：Hooper(1..7)、睡眠/HRV 枚举、Journal 事件、女性周期。

2) 后端持久化（建议字段）
   - `training_label: string`（无/低/中/高/极高，作为回退输入）
   - `rpe_0_10: number`，`duration_min: number`（两者都有时计算）
   - `daily_au: number`（= RPE × 时长，由后端计算）
   - 日级滚动保存，便于聚合出近 28 天 AU 列表。

3) 服务/API 调用（与引擎对接）
   - 优先传 `recent_training_au: number[]`（近 28 天日 AU）
   - 无 AU 时回退传 `recent_training_loads: string[]`（无/低/中/高/极高）
   - 其他证据按需传入（见“API 请求字段”）。

4) 引擎计算
   - 先验：基线转移 + 训练负荷 CPT + 连天高强惩罚 + 小幅 ACWR 调节（以慢性保护为主）+ 昨日日志短期影响。
   - 后验：Hooper/睡眠/HRV 等条件概率表融合，月经周期（可选）以连续似然参与。

5) 返回结果
   - 分数（0..100）、诊断状态、先验/后验分布、更新历史、下一日 `previous_state_probs`。

---

## API 请求字段（payload = 请求体 JSON）
- 基本：
  - `user_id: string`，`date: YYYY-MM-DD`，`gender: string`（“男”/“女”）
  - `previous_state_probs: object`（状态名→概率，六键：Peak/Well-adapted/FOR/Acute Fatigue/NFOR/OTS；首日可用默认 `{Peak:0.1, Well-adapted:0.5, FOR:0.3, Acute Fatigue:0.1, NFOR:0, OTS:0}`）

- 训练负荷（2 选 1，优先 AU）：
  - `recent_training_au?: number[]`（近 28 天日 AU，AU=RPE×时长；历史 <7 天时不启用 ACWR）
  - `recent_training_loads?: string[]`（回退；无/低/中/高/极高；亦用于“连续训练惩罚”）
  - `training_load?: string`（当天标签，供细化用）

- Journal（昨天，统一 JSON）：
  - 短期（仅影响今天先验，用后自动清除）：`alcohol_consumed`，`late_caffeine`，`screen_before_bed`，`late_meal`，以及其它自定义键（默认只记录与清除，不参与计算，除非加入白名单）
  - 持续（仅影响今天后验，直到显式取消）：`is_sick`，`is_injured`

- 后验证据（今天）：
  - `objective: { sleep_performance_state, restorative_sleep, hrv_trend }`
  - `hooper: { fatigue, soreness, stress, sleep }`（1..7）
  - `cycle?: { day, cycle_length }`（女性，可选）

- Response（JSON）：
  - `prior_probs`（今天先验），`final_posterior_probs`（今天后验）
  - `final_readiness_score`，`final_diagnosis`
  - `evidence_pool`，`update_history`
  - `next_previous_state_probs`（给明天做 `previous_state_probs`）

- 行为说明（服务内部）：
  - 先验（今天）= `previous_state_probs` × 基线转移 × `training_load（昨天）` × `journal（昨天短期项）` × 小幅 ACWR 调节（如 AU 历史≥7 天）。
  - 后验（今天）= 先验 × `objective（今天）` × `hooper（今天）` × `cycle（今天）` × `journal（昨天持续项若仍有效）`。
  - 短期项用后自动清除；持续项持续生效直到某日显式设为 false。

示例（请求 JSON）：
```json
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
```

---

## Journal 政策（自定义/清除策略/计算白名单）
- Journal 支持上百种键，并允许自定义扩展。
- 默认只有两类键是“持续项”：`is_sick`、`is_injured`（进入当天后验，持续生效，直到某天在 journal 中取消）。
- 其余一律按“短期项”处理：仅影响一次（作为昨天→今天的先验），在用于昨天的存储中自动清除；但所有原始记录都保存在 `user_daily.journal` 里，供回顾分析。
- 计算白名单（默认）：
  - 短期参与先验：`alcohol_consumed`，`late_caffeine`，`screen_before_bed`，`late_meal`
  - 持续参与后验：`is_sick`，`is_injured`
- 其它短期键（如 `high_stress_event_today`，`meditation_done_today`）默认仅记录与清除，不参与计算；若业务将来需要，可加入白名单或在引擎侧增加相应 CPT/似然映射后启用。

---

## 引擎运行逻辑（自然语言）
1) 先验（Prior）
   - 基线转移：依据上一日状态分布与状态转移表。
   - 训练负荷：按“当天标签”与“近期标签/或 AU 序列”进行先验修正，包含“连续高强”的惩罚。
   - ACWR 小幅调节（A7/C28）：
     - 稳态（0.9–1.1）不动；
     - 急性高 + 慢性低 → 轻惩罚（-1..-2 分）；
     - 急性高 + 慢性高 → 慢性保护（惩罚减半或接近不动）；
     - 急性低（≤0.9）→ 小奖励（≈+1 分）；
     - 极低急性 + 慢性低 → 极轻微去适应（<1 分）。
     - 保险：`recent_training_au` 少于 7 天时不启用 ACWR（中性）。
   - 日志（昨日短期）：酒精/晚咖/睡前屏幕/晚餐，影响今日先验；今日持久状态（生病/受伤）不进先验，在后验阶段生效。

2) 后验（Posterior）
   - Hooper（1..7）与睡眠/HRV 等证据按 CPT 融合，月经周期（如提供）以连续似然参与。
   - 证据权重统一配置于 `constants.py`。

3) 结果
   - 返回当日分数与诊断，并提供下一日 `previous_state_probs` 以便链式调用。

---

## 文件/模块说明
- `readiness/service.py`：统一入口 `compute_readiness_from_payload(payload: dict)`；将请求拆分为引擎先验/后验输入，负责 Journal“昨晚/今晨”的写入与分类。
- `readiness/engine.py`：先验/后验编排，含 ACWR 调节/连天高强惩罚/Journal 清除/证据融合/周期连续似然；`JournalManager` 为内存实现，可替换为持久层。
- `readiness/mapping.py`：原始值→枚举：睡眠表现、恢复性睡眠、HRV 趋势；Hooper 连续/分档映射。
- `readiness/hooper.py`：Hooper 映射：分档（1–2 低、3–5 中、6–7 高）且同档内有层次。
- `readiness/constants.py`：CPT、证据权重、冷启动“标签→AU”映射（无0/低200/中350/高500/极高700）。
- 工具：
  - `readiness/gui_daily_sim.py`：本地 GUI，用于手工逐日模拟（可选）。
  - `readiness/simulate_days_via_service.py`：批量生成 10/30 天数据用于回归验证。
  - `readiness/exp_*`：实验脚本（Hooper/ACWR 敏感性）。

---

## 示例与注意事项
- 请求样例（AU 形态）：`readiness/examples/male_request.json`、`readiness/examples/female_request.json`
- 输出/历史示例：`readiness/examples/sim_user*_*.csv/.jsonl`
- 新用户无历史也可运行：`recent_training_au` < 7 天时不启用 ACWR，逻辑保持中性。
- 建议后端尽早累积 `daily_au`，以便触发“慢性保护”。
- 连续运行多天：将 `next_previous_state_probs` 作为下一日 `previous_state_probs`。
