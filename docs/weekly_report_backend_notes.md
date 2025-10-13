# Weekly Report Backend Notes

## Field add-ons & storage
- readiness payload 支持自由文本字段 `report_notes`（`ReadinessState.raw_inputs.report_notes`），Phase 4/5 会引用。
- **Report notes 持久化**：推荐在 `user_daily` 新增 `report_notes` 列（TEXT/JSONB），读取 readiness payload 时原样透传。
- **Lifestyle 标签规范**：`journal.lifestyle_tags[]` 支持前缀，例如 `sport:tennis`、`strength:legs`、`travel` 等。聚合到周报时写入 `history[i].lifestyle_events[]`，供洞察/Planner 使用。
- **Training sessions（可选）**：周报不强依赖训练 session 明细；如需补充类型/部位，可在 `user_daily.objective.training_sessions[]`（JSON）或独立表记录 `type_tags[]`，聚合时同样写入 `history[].lifestyle_events[]`。

## Phase 1 Payload (Ingest) Example
来自 readiness 数据库的“今日”原始数据（可选）+ 近 7 天历史（必需），一次性返回给周报流水线：

```json
{
  "user_id": "athlete_001",
  "date": "2025-09-15",
  "gender": "男性",
  "total_sleep_minutes": 420,
  "in_bed_minutes": 480,
  "deep_sleep_minutes": 110,
  "rem_sleep_minutes": 95,
  "apple_sleep_score": 84,
  "hrv_rmssd_today": 63,
  "hrv_rmssd_3day_avg": 62,
  "hrv_rmssd_7day_avg": 60,
  "hrv_rmssd_28day_avg": 62.5,
  "hrv_rmssd_28day_sd": 6.3,
  "sleep_baseline_hours": 7.6,
  "sleep_baseline_eff": 0.87,
  "rest_baseline_ratio": 0.37,
  "hrv_baseline_mu": 63,
  "hrv_baseline_sd": 5.8,
  "recent_training_au": [300, 350, 450, 0, 0, 0, 350],
  "hooper": {"fatigue": 6, "soreness": 5, "stress": 3, "sleep": 4},
  "journal": {
    "alcohol_consumed": false,
    "late_caffeine": false,
    "screen_before_bed": true,
    "late_meal": false,
    "lifestyle_tags": ["sport:tennis"],
    "sliders": {"fatigue_slider": 6, "mood_slider": 3}
  },
  "report_notes": "周三网球后加了一次腿部力量，晚上熬夜，周五周六安排了恢复日。",
  "history": [
    {
      "date": "2025-09-09",
      "readiness_score": 72,
      "readiness_band": "Well-adapted",
      "hrv_rmssd": 64,
      "hrv_z_score": 0.2,
      "sleep_duration_hours": 7.6,
      "sleep_total_minutes": 456,
      "sleep_deep_minutes": 110,
      "sleep_rem_minutes": 95,
      "daily_au": 300,
      "acwr": null,
      "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": ["sport:tennis"]
    },
    {
      "date": "2025-09-10",
      "readiness_score": 70,
      "readiness_band": "Well-adapted",
      "hrv_rmssd": 63,
      "hrv_z_score": 0.1,
      "sleep_duration_hours": 7.4,
      "sleep_total_minutes": 444,
      "sleep_deep_minutes": 105,
      "sleep_rem_minutes": 92,
      "daily_au": 350,
      "acwr": null,
      "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": ["sport:tennis"]
    },
    {
      "date": "2025-09-11",
      "readiness_score": 66,
      "readiness_band": "FOR",
      "hrv_rmssd": 61,
      "hrv_z_score": -0.2,
      "sleep_duration_hours": 6.0,
      "sleep_total_minutes": 360,
      "sleep_deep_minutes": 80,
      "sleep_rem_minutes": 75,
      "daily_au": 450,
      "acwr": null,
      "hooper": {"fatigue": 4, "soreness": 4, "stress": 3, "sleep": 6},
      "lifestyle_events": ["sport:tennis", "strength:legs", "late_night"]
    },
    {
      "date": "2025-09-12",
      "readiness_score": 62,
      "readiness_band": "FOR",
      "hrv_rmssd": 59,
      "hrv_z_score": -0.4,
      "sleep_duration_hours": 7.2,
      "sleep_total_minutes": 432,
      "sleep_deep_minutes": 95,
      "sleep_rem_minutes": 85,
      "daily_au": 0,
      "acwr": null,
      "hooper": {"fatigue": 5, "soreness": 4, "stress": 3, "sleep": 6},
      "lifestyle_events": ["fatigue_day"]
    },
    {
      "date": "2025-09-13",
      "readiness_score": 65,
      "readiness_band": "FOR",
      "hrv_rmssd": 60,
      "hrv_z_score": -0.3,
      "sleep_duration_hours": 7.8,
      "sleep_total_minutes": 468,
      "sleep_deep_minutes": 100,
      "sleep_rem_minutes": 90,
      "daily_au": 0,
      "acwr": null,
      "hooper": {"fatigue": 4, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": []
    },
    {
      "date": "2025-09-14",
      "readiness_score": 68,
      "readiness_band": "Well-adapted",
      "hrv_rmssd": 62,
      "hrv_z_score": -0.1,
      "sleep_duration_hours": 8.0,
      "sleep_total_minutes": 480,
      "sleep_deep_minutes": 105,
      "sleep_rem_minutes": 95,
      "daily_au": 0,
      "acwr": null,
      "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": []
    },
    {
      "date": "2025-09-15",
      "readiness_score": 70,
      "readiness_band": "Well-adapted",
      "hrv_rmssd": 63,
      "hrv_z_score": 0.0,
      "sleep_duration_hours": 7.6,
      "sleep_total_minutes": 456,
      "sleep_deep_minutes": 110,
      "sleep_rem_minutes": 92,
      "daily_au": 350,
      "acwr": null,
      "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": ["sport:tennis"]
    }
  ]
}
```

## Rule Updates
- Added five Phase 3 rule blocks (recovery matrix, sleep x lifestyle, subjective priority, lifestyle trend, objective vs subjective conflict) while retaining existing rules.

## Weekly Report Pipeline (Phase 4)
- `weekly_report/trend_builder.py` generates default charts（准备度趋势、准备度 vs HRV、HRV、睡眠时长/结构、训练负荷、Hooper、生活方式时间线）。
- `weekly_report/pipeline.generate_weekly_report` 调用 Gemini 构建 Analyst / Communicator / Critique 输出，未配置 LLM 时自动回退 heuristic。
- 新增脚本 `samples/generate_weekly_report_samples.py` 可生成周报样例（输出存储在 `samples/weekly_report_sample.json`）。

## Phase 5（Finalizer 已上线）
- `weekly_report/finalizer.generate_weekly_final_report` 调用 Gemini（若失败则使用模板 fallback），把 Phase 4 结果 + 准备度历史 + 训练/自由备注整合为最终 Markdown/HTML。
- 最终输出模型 `WeeklyFinalReport`：
  ```json
  {
    "markdown_report": "...",
    "html_report": "...",
    "chart_ids": ["readiness_trend", "readiness_vs_hrv", ...],
    "call_to_action": ["训练负荷管理：…", ...]
  }
  ```
- 示例脚本 `samples/generate_weekly_report_samples.py` 会同时写出 `weekly_report_final_sample.json` 与 `.md` 供前端/教练端预览。

### 数据库存储建议
1. **report_notes 持久化（Phase 1 输入）**
   - 表 `user_daily` 新增列 `report_notes` TEXT/JSONB。
   - readiness 微服务读取该列并填入 readiness payload → `ReadinessState.raw_inputs.report_notes`。
   - 周报微服务在构建 Phase 4/5 请求时必须一起传递。

2. **WeeklyFinalReport 持久化（Phase 5 输出）**
   - 建议建立新表 `weekly_reports`（或在现有周报表中新增列）存储 Phase 5 完整结果；推荐字段：
     | 列名 | 类型 | 说明 |
     | --- | --- | --- |
     | `user_id` | VARCHAR | 用户 ID |
     | `week_start` | DATE | 周期起始日 |
     | `week_end` | DATE | 周期结束日 |
     | `report_version` | VARCHAR | 生成器版本（例如 `finalizer@0.1.0`） |
     | `report_payload` | JSONB | `WeeklyFinalReport` 原始 JSON |
     | `markdown_report` | TEXT | 直接存放 Markdown（冗余字段，方便审阅/下载） |
     | `created_at` | TIMESTAMP | 生成时间 |
   - 上述 `report_payload` 应完整保存 `markdown_report/html_report/chart_ids/call_to_action`，以便前端、订阅服务或后续分析直接复用。

3. **接口输出与渲染要点**
   - 周报 API 返回 `phase3_state`、`package`、`final_report`。`final_report.markdown_report` 已包含固定图表锚点 `[[chart:<id>]]`，前端按锚点替换成图表组件。
   - 图表数据在 `package.charts[]`（`ChartSpec`）；全局推荐顺序在 `final_report.chart_ids`。
   - Planner 在 `phase3_state.next_week_plan` 中输出周目标/原则/分日强度，Finalizer 已渲染到 Markdown 的“下周行动计划”段落。

### LLM 模型配置
- 通过环境变量 `READINESS_LLM_MODEL` 设置主模型（默认 `gemini-2.5-flash`），`READINESS_LLM_FALLBACK_MODELS` 指定备选列表（逗号分隔）。
- 若未设置或模型不可用，服务会自动回退至规则生成；调试时可直接传 `use_llm=false`。
- 生产环境在容器/服务配置中注入 `GOOGLE_API_KEY` 与上述模型变量即可，无需修改代码。

> **预留扩展**：若之后需要通知/跟进/反馈，可复用原设计（Notification / Follow-up Script / Feedback Summary）并追加至 Finalizer 之后。

## Next Steps
- Database team adds storage for `report_notes`.
- Weekly report service loads historical readiness data, appends `report_notes`, and calls the readiness scoring API as before。
- **新增**：周报服务需同步聚合近 7/28 天的 `final_readiness_score`（及 band/诊断），构建 `WeeklyHistoryEntry` 时写入 `readiness_score` / `readiness_band`，以支持准备度趋势图与文案分析。
- **Phase 5 接入时**：
  1. 完善 API → 数据库的保存逻辑，将 `WeeklyFinalReport` JSON 与 Markdown 入库；
  2. 为前端/订阅端提供读取接口（例如 `GET /weekly-reports/{user_id}?week=...`），返回 Phase 5 成品；
  3. 在自动化流程中确保当周周报生成成功后即写入数据库，并记录版本与生成时间，便于追溯。
- Future Phase 4/5 outputs (weekly summary, report narratives) will be documented here once implemented.
