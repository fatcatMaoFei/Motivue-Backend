# Weekly Report Output

- Source JSON: `response_1762607068504.json`
- This document contains the extracted `final_report.markdown_report` and a ready-to-use test JSON payload for Swagger UI.

## Final Report (Markdown)

# 周报总览（2025-10-18）

## 本周概览
- 本周训练总体情况：共 7 个训练日，训练量 (AU) 区间为 120 AU 至 500 AU，周中负荷较高，周末安排了恢复日。
- 周均准备度与范围：本周平均准备度为 80.3 分，范围在 72.0 分至 88.0 分之间，整体呈现周中下降、周末回升的趋势 [[chart:readiness_trend]]。
- ACWR 状态与风险提醒：本周 ACWR 维持在 0.83 的最佳区间，最新 ACWR 约为 0.92 [[chart:training_load]]。ACWR 处于健康范围，但周中负荷集中导致了恢复压力。
- 关键生活方式驱动及恢复重点：本周生活方式事件包括旅行、网球训练、腿部力量训练，以及周末的恢复日 [[chart:lifestyle_timeline]]。周末通过主动恢复，身体状态得到显著回升。

## 训练负荷与表现
| 日期 | 训练量 (AU) | 准备度分数 / 分档 | 生活方式事件 / 备注 |
| --- | --- | --- | --- |
| 10-12 | 310.0 | 88.0 / Peak | travel |
| 10-13 | 360.0 | 84.0 / Well-adapted | - |
| 10-14 | 420.0 | 79.0 / FOR | sport:tennis |
| 10-15 | 500.0 | 72.0 / Acute Fatigue | strength:legs |
| 10-16 | 220.0 | 74.0 / FOR | - |
| 10-17 | 180.0 | 80.0 / Well-adapted | - |
| 10-18 | 120.0 | 85.0 / Well-adapted | recovery_day |
- 每日重点
  - 10-12: 训练量 310 AU，准备度 88 分（Peak），当日有旅行事件，次日准备度略有下降。
  - 10-13: 训练量 360 AU，准备度 84 分（Well-adapted），负荷开始增加，身体状态良好。
  - 10-14: 训练量 420 AU，准备度 79 分（FOR），当日进行网球训练，负荷持续增加，准备度进入恢复需求区。
  - 10-15: 训练量高达 500 AU，准备度降至 72 分（Acute Fatigue），当日进行腿部力量训练，高负荷叠加导致身体进入急性疲劳状态。
  - 10-16: 训练量降至 220 AU，准备度回升至 74 分（FOR），开始进入恢复阶段。
  - 10-17: 训练量 180 AU，准备度回升至 80 分（Well-adapted），身体恢复持续向好。
  - 10-18: 训练量 120 AU，准备度回升至 85 分（Well-adapted），当日安排恢复日，身体状态显著改善。
- 其它训练洞察
  - 本周 ACWR (Acute:Chronic Workload Ratio，急性慢性负荷比) 维持在 0.83 的最佳区间，表明整体负荷管理良好，但周中（10-14至10-15）负荷集中，ACWR 曾达到 1.28，接近疲劳风险阈值 [[chart:training_load]]。
  - 连续高负荷（10-13至10-15日训练量从 360 AU 增至 500 AU）导致准备度从 84 分骤降至 72 分，提示在高负荷期需更严格管理单日负荷与恢复。

## 恢复与生理信号
| 日期 | HRV (RMSSD) | Z-score | 训练 / 事件备注 |
| --- | --- | --- | --- |
| 10-12 | 86.0 | null | 310 AU / travel |
| 10-13 | 83.0 | null | 360 AU |
| 10-14 | 74.0 | null | 420 AU / sport:tennis |
| 10-15 | 68.0 | null | 500 AU / strength:legs |
| 10-16 | 70.0 | null | 220 AU |
| 10-17 | 76.0 | null | 180 AU |
| 10-18 | 82.0 | null | 120 AU / recovery_day |
- HRV 与训练/事件的关系
  - 本周 HRV (RMSSD) 趋势与准备度高度一致，从 10-12 的 86.0 ms 降至 10-15 的 68.0 ms，并在周末回升至 82.0 ms [[chart:hrv_trend]]。这表明身体对周中高负荷的生理应激反应明显。
  - 遗憾的是，HRV Z-score (心率变异性相对于你长期平均水平的偏离程度) 数据缺失，这限制了我们对你每日恢复状态的精细评估。若有数据，Z-score 低于 -0.5 通常提示恢复不足。
- 休息/低负荷日后的恢复成效显著：在 10-16 日开始降低负荷后，准备度从 72 分回升至 10-18 日的 85 分（提升 13 分），HRV (RMSSD) 从 68.0 ms 回升至 82.0 ms（提升 14 ms），主观疲劳度也从 5 降至 2，酸痛从 5 降至 2，显示了良好的恢复能力， Hooper 主观反馈与客观指标高度对齐。
| 日期 | 睡眠时长 (h) | 深睡 (min) | REM (min) | 事件 |
| --- | --- | --- | --- | --- |
| 10-12 | 7.9 | null | null | travel |
| 10-13 | 7.4 | null | null | - |
| 10-14 | 6.9 | null | null | sport:tennis |
| 10-15 | 6.6 | null | null | strength:legs |
| 10-16 | 7.0 | null | null | - |
| 10-17 | 7.6 | null | null | - |
| 10-18 | 8.2 | null | null | recovery_day |
- 睡眠与训练/事件的关系
  - 周中高负荷日（10-15日，500 AU）与最低睡眠时长 6.6 小时相关，远低于 7.6 小时的基线，这可能是导致准备度与 HRV 下降的关键因素之一 [[chart:sleep_duration]]。
  - 经过周末的低负荷与恢复日，睡眠时长显著回升至 8.2 小时，超过基线 0.6 小时，有效促进了身体的恢复。
  - 深睡和 REM 睡眠数据缺失，影响了对睡眠质量的全面评估。

## 主观反馈（Hooper 指数）
| 日期 | 疲劳 | 酸痛 | 压力 | 睡眠质量 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 10-12 | 2.0 | 2.0 | 2.0 | 6.0 | 旅行 |
| 10-13 | 3.0 | 3.0 | 3.0 | 6.0 | 训练量增加 |
| 10-14 | 4.0 | 4.0 | 3.0 | 5.0 | 网球训练 |
| 10-15 | 5.0 | 5.0 | 4.0 | 4.0 | 高负荷腿部力量训练 |
| 10-16 | 4.0 | 3.0 | 3.0 | 5.0 | 负荷降低 |
| 10-17 | 3.0 | 2.0 | 3.0 | 6.0 | 恢复中 |
| 10-18 | 2.0 | 2.0 | 2.0 | 6.0 | 恢复日 |
- Hooper 四项趋势总结
  - 疲劳、酸痛和压力评分在周中高负荷日（10-15）达到峰值（疲劳 5，酸痛 5，压力 4），与客观准备度、HRV 和睡眠的下降趋势高度吻合 [[chart:hooper_radar]]。
  - 睡眠质量评分在 10-15 日降至最低（4），也与当日实际睡眠时长不足相符。随着周末负荷降低和恢复，各项 Hooper 指标均显著改善，显示主观感受与生理数据同步。

## 生活方式事件
- 10-12: travel → 次日准备度从 88 降至 84，HRV 从 86 降至 83。
- 10-14: sport:tennis → 次日训练量达 500 AU，准备度从 79 降至 72，HRV 从 74 降至 68，睡眠时长从 6.9h 降至 6.6h。
- 10-15: strength:legs → 当日高负荷训练与睡眠不足叠加，导致各项恢复指标达到周内最低点。
- 10-18: recovery_day → 当日各项恢复指标显著回升，准备度、HRV 和睡眠时长均达到周内较高水平。

## 自由备注与训练日志洞察
- 周中（10-14至10-15）的网球和腿部力量训练叠加高训练量，对身体造成了较大冲击，导致准备度、HRV 和睡眠的显著下降。
- 周末安排恢复日是明智之举，有效促进了身体从周中疲劳中恢复，使各项指标迅速回升。

## 相关性洞察
- 高训练负荷是影响恢复的关键因素：10-15日高达 500 AU 的训练量与最低的准备度 (72)、HRV (68) 和睡眠时长 (6.6h) 密切相关，同时主观疲劳、酸痛和压力评分也达到峰值，表明身体处于急性疲劳状态。
- 休息日后的恢复成效显著：经过 10-16 日开始的负荷降低和 10-18 日的恢复日，准备度从 72 分回升至 85 分（+13 分），HRV (RMSSD) 从 68 ms 回升至 82 ms（+14 ms），睡眠时长从 6.6 小时增至 8.2 小时（+1.6 小时），Hooper 指标也同步改善，显示了良好的恢复能力和对低负荷的积极响应。
- 生活方式事件与训练负荷的叠加效应：旅行、网球和腿部力量训练等生活事件与训练负荷叠加，加剧了周中身体的疲劳程度，提示在安排训练时需充分考虑这些额外压力源。
- 触发阈值提醒：当准备度低于 70 分（FOR 档）或 65 分（Acute Fatigue 档）时，应高度关注恢复；若 HRV Z-score（心率变异性相对于你长期平均水平的偏离程度）低于 -0.5，或 Hooper 疲劳评分高于 5，则需考虑调整训练计划或增加恢复措施。

## 下周行动计划
下周总体建议：冲击周，但需密切关注恢复。
本周 ACWR 维持在 0.83 的最佳区间，周末身体已良好回升（HRV 82 ms，睡眠 8.2h，主观疲劳低），为下周冲击提供了良好基础，但需吸取周中负荷集中导致恢复不足的教训。
- **负荷管理**：建议将高强度训练日控制在每周 2 天以内，且高强度日之间至少间隔 48 小时。整体训练量可逐步提升 10%~15% (冲击周指引)，但需密切关注身体反馈，以中等强度训练为主。
- **部位均衡**：考虑到本周有腿部力量训练，请在下周冲击周的训练安排中注意全身肌肉群的均衡发展，避免过度侧重某一区域，以预防局部疲劳和损伤。
- **恢复优先**：鉴于本周中期的经验，在高负荷训练日后，请务必确保有充足的睡眠和主动恢复时间。周末的恢复日安排非常有效，请继续保持。
- **每日调整策略**：密切关注每日准备度、HRV 和主观疲劳度。如果准备度低于 65，或 HRV Z-score 低于 -0.5，或主观疲劳度（Hooper 评分）高于 5，请考虑将当日训练强度降低一档或改为主动恢复。
- **睡眠卫生**：持续强化睡眠卫生管理，目标是每晚睡眠时长达到或超过 7.6 小时基线。高质量的睡眠是高效恢复的基石。
本段不替代教练排期，属于建议与原理说明。

## 鼓励与后续
本周你展现了出色的恢复能力，尤其是在周中高负荷后能迅速调整，使各项指标在周末回升至良好水平，这非常值得肯定！下周进入冲击周，请继续保持这份积极性，并严格执行负荷管理和恢复策略。我们将重点关注你的每日准备度、HRV 变化以及睡眠质量，确保你在提升表现的同时，维持身体的健康与平衡。期待你下周的精彩表现！

---

## Test Request JSON (for Swagger)

```json
{
  "payload": {
    "user_id": "athlete_001",
    "date": "2025-10-18",
    "sleep_baseline_hours": 7.6,
    "hrv_baseline_mu": 78,
    "report_notes": "周三网球+腿部力量，周末安排恢复日。",
    "journal": {
      "lifestyle_tags": ["sport:tennis", "strength:legs", "travel"]
    },
    "recent_training_au": [310, 280, 0, 450, 500, 360, 200, 0, 420, 380, 250, 0, 390, 360, 280, 320, 410, 0, 460, 350, 290, 0, 300, 370, 320, 330, 0, 410],
    "history": [
      {"date": "2025-10-12", "readiness_score": 88, "readiness_band": "Peak", "hrv_rmssd": 86, "sleep_duration_hours": 7.9, "daily_au": 310, "acwr": 0.98, "hooper": {"fatigue": 2, "soreness": 2, "stress": 2, "sleep": 6}, "lifestyle_events": ["travel"]},
      {"date": "2025-10-13", "readiness_score": 84, "readiness_band": "Well-adapted", "hrv_rmssd": 83, "sleep_duration_hours": 7.4, "daily_au": 360, "acwr": 1.02, "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 6}, "lifestyle_events": []},
      {"date": "2025-10-14", "readiness_score": 79, "readiness_band": "FOR", "hrv_rmssd": 74, "sleep_duration_hours": 6.9, "daily_au": 420, "acwr": 1.14, "hooper": {"fatigue": 4, "soreness": 4, "stress": 3, "sleep": 5}, "lifestyle_events": ["sport:tennis"]},
      {"date": "2025-10-15", "readiness_score": 72, "readiness_band": "Acute Fatigue", "hrv_rmssd": 68, "sleep_duration_hours": 6.6, "daily_au": 500, "acwr": 1.28, "hooper": {"fatigue": 5, "soreness": 5, "stress": 4, "sleep": 4}, "lifestyle_events": ["strength:legs"]},
      {"date": "2025-10-16", "readiness_score": 74, "readiness_band": "FOR", "hrv_rmssd": 70, "sleep_duration_hours": 7.0, "daily_au": 220, "acwr": 1.08, "hooper": {"fatigue": 4, "soreness": 3, "stress": 3, "sleep": 5}, "lifestyle_events": []},
      {"date": "2025-10-17", "readiness_score": 80, "readiness_band": "Well-adapted", "hrv_rmssd": 76, "sleep_duration_hours": 7.6, "daily_au": 180, "acwr": 1.00, "hooper": {"fatigue": 3, "soreness": 2, "stress": 3, "sleep": 6}, "lifestyle_events": []},
      {"date": "2025-10-18", "readiness_score": 85, "readiness_band": "Well-adapted", "hrv_rmssd": 82, "sleep_duration_hours": 8.2, "daily_au": 120, "acwr": 0.92, "hooper": {"fatigue": 2, "soreness": 2, "stress": 2, "sleep": 6}, "lifestyle_events": ["recovery_day"]}
    ]
  },
  "persist": false
}
```
