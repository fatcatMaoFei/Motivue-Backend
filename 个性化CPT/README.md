个性化CPT（交付与使用指南）

目的
- 提供“CSV 历史 → 个性化 CPT JSON”的离线训练能力；产物用于准备度服务的热替换。
- 默认个性化强度 k=50（适合 Hooper/HRV/睡眠等日更证据场景）。

目录结构（关键）
- 个性化CPT/personalize_cpt.py        单用户：CSV → CPT JSON（默认 k=50）
- 个性化CPT/monthly_update.py          月度批量更新（近 N 天滚动窗口）
- 个性化CPT/clean_history.py           清洗 Excel/GUI 导出为标准列
- 个性化CPT/PERSONALIZATION_README.md  详细规格与 FAQ
- 个性化CPT/artifacts/                  训练输入/输出产物统一存放位置（CSV/JSON/汇总）

快速开始
- GUI 录入测试（可选）
  - pip install -r gui/requirements.txt
  - streamlit run gui/app.py
  - 侧栏可设置 CSV 保存路径（默认：个性化CPT/artifacts/history_gui_log.csv）
- 单用户训练（默认 k=50）
  - python 个性化CPT/personalize_cpt.py --csv 个性化CPT/artifacts/history_gui_log.csv `
    --user u001 --out 个性化CPT/artifacts/personalized_emission_cpt_u001.json

月度批量更新（推荐）
- 从数据库按用户导出近 90 天 CSV（每用户一份、标准列），放到某目录（如 /data/readiness_exports）。
- 一条命令批量训练并输出汇总：
  - python 个性化CPT/monthly_update.py --input-dir /data/readiness_exports --since-days 90 --k 50 --user-col user_id
- 输出位置：个性化CPT/artifacts/YYYYMM/
  - personalized_emission_cpt_<user>.json（个性化 CPT）
  - monthly_summary.csv（user_id, days_used, k, 产物路径）
- 约束：样本 <30 天跳过；其余证据 <10 样本保持默认 CPT。

CSV 标准字段（日一行）
- 基本：date(YYYY-MM-DD), user_id, gender(男性|女性)
- 训练负荷（今日先验）：training_load(极高|高|中|低|休息)
- 睡眠（后验，二选一 + 恢复性保留）：
  - apple_sleep_score(0–100) 或 sleep_performance_state(good|medium|poor)
  - restorative_sleep(high|medium|low)
- HRV（后验）：hrv_trend(rising|stable|slight_decline|significant_decline)
- Hooper（后验）：fatigue_hooper, soreness_hooper, stress_hooper, sleep_hooper（1..7）
- 其他（后验）：nutrition(adequate|inadequate_mild|inadequate_moderate|inadequate_severe), gi_symptoms(none|mild|severe)
- 可选布尔（后验）：is_sick, is_injured, high_stress_event_today, meditation_done_today（True/False）
- 缺失：空串/None/NULL/NA/NaN 均可，个性化仅对有数据天数计数；<10 样本不更新该证据。

准备度服务对接（热替换方式）
- 简单加载（本地/脚本）
  - from readiness.personalization_simple import load_personalized_cpt
  - load_personalized_cpt('个性化CPT/artifacts/202509/personalized_emission_cpt_u001.json')
- 生产建议
  - 存储：写入 readiness.cpt_table（user_id, cpt_json, trained_at, version）或对象存储
  - 通知：训练完成后通过 MQ 触发服务端“按 user_id 载入/刷新缓存”
  - 回退：找不到用户CPT时使用默认全局CPT

为何选择 k=50
- Hooper/HRV/睡眠等“日更”证据在 30–90 天内能体现清晰个性化，同时保持稳健；
- 若希望更“快更强”，可用 --k 30；若更稳，可继续使用 50。

附：清洗工具
- 将桌面/Excel/GUI 导出的 CSV 清洗为标准字段：
  - python 个性化CPT/clean_history.py --in C:/path/raw.csv --out 个性化CPT/artifacts/history_gui_log_clean.csv

备注
- 建议在仓库 .gitignore 中忽略 个性化CPT/artifacts 下的 *.csv 与 *.json（避免产物进入版本库）。
