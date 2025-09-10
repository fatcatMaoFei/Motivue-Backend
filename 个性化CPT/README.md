个性化CPT（交付与使用指南）

目的
- 提供“CSV 历史 → 个性化 CPT JSON”的离线训练与交付产物，便于后端直接对接数据库与部署。

目录说明
- personalized_emission_cpt_standard_user.json：用 60 天样例训练得到的个性化 EMISSION_CPT。
- history_60d_backend.csv：强制“苹果分 vs 传统睡眠”二选一后的历史样例。
- example_request.json：一天的在线计算请求示例（苹果分 + 恢复性 + HRV + Hooper）。
- apply_cpt.py：本地将个性化 CPT 载入内存（演示）。
- personalize_cpt.py：主入口（CSV → CPT JSON）。
- PERSONALIZATION_README.md：详细字段规范、流程与FAQ。

环境要求
- Python 3.9+
- 依赖：pandas（可选：sqlalchemy 若直接从DB拉取）
- 在仓库根目录下运行命令，确保可导入 readiness 包。

数据格式（日一行，固定列名）
- 必备：date(YYYY-MM-DD), user_id, gender(男性|女性)
- 先验：training_load(极高|高|中|低|休息)
- 睡眠（二选一）：apple_sleep_score 或 sleep_duration_hours + sleep_efficiency
- 恢复性：restorative_ratio(0..1)
- HRV：hrv_trend（或留空）
- Hooper(1..7)：fatigue_hooper, soreness_hooper, stress_hooper, sleep_hooper
- 其他：nutrition, gi_symptoms, alcohol_consumed, late_caffeine, screen_before_bed, late_meal, is_sick, is_injured
- 空值：空串/None/NULL/NA/NaN 均可

训练：CSV → CPT JSON
- 基本：
  - python 个性化CPT/personalize_cpt.py --csv 个性化CPT/history_60d_backend.csv --user u001 --out 个性化CPT/personalized_emission_cpt_u001.json --shrink-k 100
  - 或者将你们数据库导出的标准CSV路径替换为自有路径。

产物与部署
- 输出：个性化 CPT JSON，仅包含 EMISSION_CPT。
- 存储：建议版本化入库（user_id, cpt_json, trained_at, days_used, shrink_k）。
- 应用：
  - 本地演示加载：python 个性化CPT/apply_cpt.py 个性化CPT/personalized_emission_cpt_u001.json
  - 服务热替换：计算服务按 user_id 加载用户 CPT；无则回退默认。可结合消息队列广播更新。

更多细节、字段定义、流程与FAQ 请见：个性化CPT/PERSONALIZATION_README.md。
