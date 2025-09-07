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
