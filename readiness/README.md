# Readiness（就绪度）模块

一个自包含的贝叶斯就绪度计算引擎及其辅助工具。从旧版动态模型中抽取并整理为独立包，便于调用与维护。

## 快速开始
- Python 3.11+
- 可选依赖：`numpy`、`pandas`（仅其他模块可能用到，本目录核心不强制要求）

示例（以统一负载一次性计算）：
```python
from readiness.service import compute_readiness_from_payload
import json

payload = json.loads(open('readiness/examples/male_request.json', 'r', encoding='utf-8').read())
res = compute_readiness_from_payload(payload)
print(res['final_readiness_score'], res['final_diagnosis'])
```

## 文件/模块说明

- service.py：
  - 作用：对外统一接口，接收一个“JSON 风格字典”并返回当天就绪度结果。
  - 入口：`compute_readiness_from_payload(payload: dict) -> dict`。
  - 关键输入（按需提供即可）：
    - 基本：`user_id: str`，`date: YYYY-MM-DD`，`gender: str`（如“男/女”）。
    - 先验相关：`previous_state_probs: {state: prob}`；`training_load: str`（如“低/中/高/极高”），`recent_training_loads: List[str]`。
    - 日志：
      - 简化统一：`journal: {alcohol_consumed, late_caffeine, screen_before_bed, late_meal, is_sick, is_injured, high_stress_event_today, meditation_done_today}`。
      - 兼容键：`journal_yesterday`、`journal_today`。
    - 观测证据：如 `sleep_performance_state`、`hrv_trend`、`nutrition`、`gi_symptoms` 等。
    - Hooper 主观量表：`hooper: {fatigue, soreness, stress, sleep}`（支持 1..7 连续映射）。
    - 月经周期（后验、连续）：`cycle: {day: int, cycle_length: int}`。
  - 输出：`prior_probs`、`final_posterior_probs`、`final_readiness_score`（0..100）、`final_diagnosis`、`update_history`、`evidence_pool`、`next_previous_state_probs` 等。

- engine.py：
  - 作用：先验/后验的核心编排逻辑。
  - 主要类/方法：
    - `ReadinessEngine(user_id, date, previous_state_probs=None, gender='男')`
      - `calculate_today_prior(causal_inputs: dict) -> Dict[state, prob]`
      - `add_evidence_and_update(new_evidence: dict) -> dict`（逐步累加证据）
      - `get_daily_summary() -> dict`（汇总先验、后验、分数、诊断、历史）
    - `JournalManager`（内存版）：`add_journal_entry`、`get_yesterdays_journal`、`get_today_journal_evidence`。

- mapping.py：
  - 作用：将原始输入映射到模型期望的枚举/变量（供发射概率表使用）。
  - 能力：
    - 将 HealthKit 风格数值转换为类别：睡眠表现、恢复性睡眠、HRV 趋势等。
    - Hooper 键：`fatigue_hooper|soreness_hooper|stress_hooper|sleep_hooper` 映射到 `subjective_*`；同时保留 1..7 分数用于连续映射。
    - 日志布尔透传：`is_sick`、`is_injured`、`high_stress_event_today`、`meditation_done_today`。

- hooper.py：
  - 作用：将 Hooper 1..7 分数通过 Bezier/伯恩斯坦权重连续映射为状态似然向量。
  - API：`hooper_to_state_likelihood(var, score) -> Dict[state, prob]`，`var ∈ {subjective_fatigue, muscle_soreness, subjective_stress, subjective_sleep}`。

- cycle.py：
  - 作用：根据周期日生成平滑的后验似然（连续）。
  - API：`cycle_likelihood_by_day(day: int, cycle_length: int = 28) -> Dict[state, prob]`。

- cycle_personalization.py：
  - 作用：极简的用户级周期个性化参数注册。
  - API：`set_user_cycle_params(user_id, ov_frac, luteal_off, sig_scale)`、`get_user_cycle_params(user_id)`。

- constants.py：
  - 作用：集中维护所有 CPT 表与权重。
  - 包含：`EMISSION_CPT`、`BASELINE_TRANSITION_CPT`、`TRAINING_LOAD_CPT`、`ALCOHOL_CONSUMPTION_CPT`、`LATE_CAFFEINE_CPT`、`SCREEN_BEFORE_BED_CPT`、`LATE_MEAL_CPT`、`MENSTRUAL_PHASE_CPT`、`CAUSAL_FACTOR_WEIGHTS`、`READINESS_WEIGHTS`、`EVIDENCE_WEIGHTS_FITNESS`。

- analytics.py：
  - 作用：回顾性、朴素地估计布尔日志项对数值指标的影响（可设时滞）。
  - API：`effect_of_journal_on_metric(jm, user_id, item_key, metric_key, start_date=None, end_date=None, lag_days=1)`。

- personalization_em_demo.py / personalization_em_demo_woman.py：
  - 作用：保持旧版示例脚本从新位置可运行的薄封装（仍复用工程根目录的原始实现）。

- examples/：
  - `male_request.json`、`female_request.json`：`service.compute_readiness_from_payload` 的示例负载。
  - `user_history_*_30days.csv`：示例 30 天历史，便于试验/排查。

## 使用范式（典型流程）
```python
from readiness.engine import ReadinessEngine

eng = ReadinessEngine(user_id='u1', date='2025-09-06')
prior = eng.calculate_today_prior({
    'training_load': '中',
    'recent_training_loads': ['高','极高','高','极高']
})
eng.add_evidence_and_update({'sleep_performance': 'medium'})
eng.add_evidence_and_update({'hrv_trend': 'slight_decline'})
summary = eng.get_daily_summary()
print(summary['final_readiness_score'], summary['final_diagnosis'])
```

## 注意事项
- 日志规则：
  - “昨天”的短期行为（如 alcohol/screen/caffeine/late_meal）影响“今天”的先验；
  - “今天”的持久状态（如 is_sick/is_injured/high_stress_event_today/meditation_done_today）作为后验证据应用。
- 证据累加是有序的，可多次调用 `add_evidence_and_update` 逐步更新。
- 连续运行多天时，可把 `final_posterior_probs` 作为下一天的 `previous_state_probs`。
- 兼容：工程根目录仍保留旧脚本；本目录提供更清晰的 API 表面。

## 相关示例脚本（工程根目录）
- `simulate_5days_via_service.py`：演示如何通过 `service` 连续跑多天。
- `demo_hooper_discrete_vs_continuous.py`：对比 Hooper 离散/连续映射效果。

