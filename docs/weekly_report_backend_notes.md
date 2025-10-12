# Weekly Report Backend Notes

## Field Additions
- readiness payload now supports an optional free-text field `report_notes` (stored at `ReadinessState.raw_inputs.report_notes`) for weekly report / LLM usage.
- Database changes are deferred, but the service team should plan to persist `report_notes` (JSON/Text column on `user_daily` or a dedicated table) and inject it into the readiness payload.
- **Update 2025-10**：数据库/API 团队需尽快在 `user_daily`（或等价的日度表）中新增列 `report_notes`（类型建议 TEXT/JSONB），写入来自客户端的自由日志文本，以便 Phase 4/5 使用。所有微服务在聚合 readiness payload 时需原样透传该字段。

## Phase 1 Payload (Ingest) Example
来自 readiness 数据库的“今日”原始数据（raw_inputs）+ 近 7 天历史（Phase 3/4/5 用），必须一次性返回给周报流水线：

```json
{
  "user_id": "athlete_001",
  "date": "2025-09-15",
  "gender": "男性",
  "total_sleep_minutes": 402,
  "in_bed_minutes": 450,
  "deep_sleep_minutes": 88,
  "rem_sleep_minutes": 78,
  "apple_sleep_score": 82,
  "hrv_rmssd_today": 57,
  "hrv_rmssd_3day_avg": 58,
  "hrv_rmssd_7day_avg": 61,
  "hrv_rmssd_28day_avg": 62.5,
  "hrv_rmssd_28day_sd": 6.3,
  "sleep_baseline_hours": 7.6,
  "sleep_baseline_eff": 0.87,
  "rest_baseline_ratio": 0.37,
  "hrv_baseline_mu": 63,
  "hrv_baseline_sd": 5.8,
  "recent_training_au": [0, 500, 420, 560, 300, 360, 440],
  "training_sessions": [
    {
      "label": "高",
      "rpe": 8,
      "duration_minutes": 70,
      "au": 560,
      "start_time": "2025-09-14T18:30:00"
    }
  ],
  "hooper": {"fatigue": 6, "soreness": 5, "stress": 3, "sleep": 4},
  "journal": {
    "alcohol_consumed": false,
    "late_caffeine": false,
    "screen_before_bed": true,
    "late_meal": false,
    "lifestyle_tags": ["work_travel"],
    "sliders": {"fatigue_slider": 6, "mood_slider": 3}
  },
  "report_notes": "昨晚赶飞机回程，入睡前加班处理工作，整体感觉疲劳较高。",
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
      "daily_au": 320,
      "acwr": null,
      "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": ["sex"]
    },
    {
      "date": "2025-09-10",
      "readiness_score": 100,
      "readiness_band": "Well-adapted",
      "hrv_rmssd": 63,
      "hrv_z_score": 0.1,
      "sleep_duration_hours": 7.4,
      "sleep_total_minutes": 444,
      "sleep_deep_minutes": 105,
      "sleep_rem_minutes": 92,
      "daily_au": 360,
      "acwr": null,
      "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": []
    },
    {
      "date": "2025-09-11",
      "readiness_score": 68,
      "readiness_band": "FOR",
      "hrv_rmssd": 62,
      "hrv_z_score": -0.1,
      "sleep_duration_hours": 7.2,
      "sleep_total_minutes": 432,
      "sleep_deep_minutes": 100,
      "sleep_rem_minutes": 90,
      "daily_au": 420,
      "acwr": null,
      "hooper": {"fatigue": 4, "soreness": 3, "stress": 3, "sleep": 7},
      "lifestyle_events": []
    },
    {
      "date": "2025-09-12",
      "readiness_score": 66,
      "readiness_band": "FOR",
      "hrv_rmssd": 61,
      "hrv_z_score": -0.3,
      "sleep_duration_hours": 7.1,
      "sleep_total_minutes": 426,
      "sleep_deep_minutes": 98,
      "sleep_rem_minutes": 88,
      "daily_au": 500,
      "acwr": 1.15,
      "hooper": {"fatigue": 5, "soreness": 4, "stress": 3, "sleep": 6},
      "lifestyle_events": ["sex"]
    },
    {
      "date": "2025-09-13",
      "readiness_score": 99,
      "readiness_band": "Acute Fatigue",
      "hrv_rmssd": 60,
      "hrv_z_score": -0.4,
      "sleep_duration_hours": 7.0,
      "sleep_total_minutes": 420,
      "sleep_deep_minutes": 95,
      "sleep_rem_minutes": 84,
      "daily_au": 560,
      "acwr": 1.32,
      "hooper": {"fatigue": 6, "soreness": 4, "stress": 4, "sleep": 6},
      "lifestyle_events": ["travel"]
    },
    {
      "date": "2025-09-14",
      "readiness_score": 64,
      "readiness_band": "Acute Fatigue",
      "hrv_rmssd": 58,
      "hrv_z_score": -0.6,
      "sleep_duration_hours": 6.8,
      "sleep_total_minutes": 408,
      "sleep_deep_minutes": 90,
      "sleep_rem_minutes": 80,
      "daily_au": 1500,
      "acwr": 1.4,
      "hooper": {"fatigue": 6, "soreness": 4, "stress": 4, "sleep": 6},
      "lifestyle_events": ["late_meal", "sex"]
    },
    {
      "date": "2025-09-15",
      "readiness_score": 100,
      "readiness_band": "Acute Fatigue",
      "hrv_rmssd": 57,
      "hrv_z_score": -0.85,
      "sleep_duration_hours": 6.7,
      "sleep_total_minutes": 402,
      "sleep_deep_minutes": 88,
      "sleep_rem_minutes": 78,
      "daily_au": 510,
      "acwr": 1.45,
      "hooper": {"fatigue": 6, "soreness": 5, "stress": 4, "sleep": 5},
      "lifestyle_events": ["travel", "sex"]
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

3. **接口输出**
   - 周报 API 在返回最新周报时可直接返回 `WeeklyFinalReport` JSON，或同时附带 Markdown，确保前端/第三方系统可以选择结构化渲染或直接显示文稿。
   - 周报微服务骨架：`weekly_report/api.py` 引入 FastAPI，提供 `POST /weekly-report/run`。请求携带 Phase 1 payload（含 `history`），可选 `use_llm`、`persist`。响应返回 Phase 3 state、Phase 4 包、Phase 5 成品，`persist=true` 时会把最终 JSON + Markdown 写入 `weekly_reports` 表。
     ```bash
     curl -X POST http://localhost:8000/weekly-report/run \
     -H "Content-Type: application/json" \
      -d '{"payload": {...}, "use_llm": true, "persist": true}'
    ```

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
