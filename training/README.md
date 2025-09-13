Training Consumption（当日训练消耗分）

目的
- 独立计算“当日消耗分”，用于前端显示“当前剩余准备度 = 准备度 − 当日消耗”。
- 不改变 readiness 的当天后验与分数，仅供展示。

默认规则（v1）
- 仅训练因子，RPE×分钟为主；label 为兜底；也接受传入 au（最后兜底）。
- 单次训练最大消耗 cap_session = 40；当日训练总消耗 cap_training_total = 60。
- 消耗曲线 g(AU)：
  - AU ≤ 150 → 0
  - 150..300 → 0..10（线性）
  - 300..500 → 10..25（线性）
  - >500 → 25..40（线性至 900 饱和）
- readiness 放大系数 scale(R) 预留，v1 固定 1.0（不随 R 变化）。

目录
- training/consumption.py        统一入口（calculate_consumption）
- training/factors/training.py   训练因子实现（RPE 为主）
- training/schemas.py            输入/输出结构

接口
- calculate_consumption(payload: TrainingConsumptionInput) -> TrainingConsumptionOutput
- 输入（关键字段）
  - user_id: str
  - date: YYYY-MM-DD
  - base_readiness_score: int（可选；若提供将顺手返回 display_readiness）
  - training_sessions: list[{
      rpe: int 1..10,
      duration_minutes: int,
      label: "极高"|"高"|"中"|"低"|"休息"（可选），
      au: float（可选），
      session_id/start_time: 可选
    }]
  - params_override: dict（可选：cap_session、cap_training_total、曲线参数等未来拓展）
- 输出
  - consumption_score: float（当日训练总消耗）
  - display_readiness: int = max(0, base_readiness_score - round(consumption_score))（若传了 base）
  - breakdown: {"training": number}
  - sessions: [{session_id, au_used, label_used, delta_consumption}]
  - caps_applied: {cap_session, cap_training_total}
  - params_used: dict（审计）

示例（Python）
```python
from training import calculate_consumption

payload = {
  "user_id": "u001",
  "date": "2025-09-12",
  "base_readiness_score": 80,
  "training_sessions": [
    {"rpe": 8, "duration_minutes": 60},
    {"label": "中", "duration_minutes": 30},
  ]
}
res = calculate_consumption(payload)
# res = {"consumption_score": 22.5, "display_readiness": 57, ...}
```

前端用法
- 初始：消耗=0 → 显示=准备度
- 标记训练：调用 calculate_consumption，刷新“当前剩余准备度”
- 多次训练：叠加（受 cap_training_total 限制）

扩展
- 预留 journal 与 device_metrics 字段，未来可接入 alcohol/steps 等新因子；
- 因子架构：training/factors/ 下新增因子，并在 consumption 中聚合求和，再套日总上限（cap_day_total，后续新增）。

