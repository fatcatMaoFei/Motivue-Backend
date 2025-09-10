Readiness 涓€у寲 CPT锛圕SV 杈撳叆 鈫?CPT JSON 杈撳嚭锛?
鐩殑
- 浠ョ粺涓€鐨勬棩绮掑害鍘嗗彶鏁版嵁锛圕SV/DB 鏍囧噯瀛楁锛変负杈撳叆锛岀绾垮涔犱釜鎬у寲 EMISSION_CPT銆?- 杈撳嚭浠呬负涓€у寲 CPT JSON锛屼笉娑夊強鍦ㄧ嚎鍑嗗搴﹁绠椼€?
鏍稿績閫昏緫
- 鏁版嵁闂ㄦ锛氭€诲ぉ鏁?鈮?30 鎵嶈繘琛屼釜鎬у寲锛涘惁鍒欑洿鎺ヤ娇鐢ㄩ粯璁?CPT銆?- 鍒嗚〃闂ㄦ锛氭瘡涓瘉鎹被鍨嬬嫭绔嬭鏁帮紝鏍锋湰閲?< 10 鐨勮〃淇濇寔榛樿涓嶆洿鏂般€?- 鏀剁缉锛坰hrinkage锛夛細伪 = n/(n+k)锛宬 榛樿 100锛涢€愮姸鎬併€侀€愮被鍒仛娣峰悎骞跺綊涓€鍖栥€?- 鐫＄湢浜岄€変竴锛氭湁 apple_sleep_score 鍒欎娇鐢ㄨ嫻鏋滃垎锛涙棤鍒欎娇鐢?sleep_performance锛堢敱鏃堕暱+鏁堢巼鏄犲皠锛夈€俽estorative_sleep 濮嬬粓淇濈暀锛屼笌鑻规灉鍒嗗苟琛屻€?
鏍囧噯杈撳叆瀛楁锛堟瘡鏃ヤ竴琛岋級
- 蹇呭锛歞ate(YYYY-MM-DD), user_id, gender(鐢锋€濂虫€?
- 鍏堥獙锛歵raining_load(鏋侀珮|楂榺涓瓅浣巪浼戞伅)锛堝彲绌猴級
- 鐫＄湢锛堜簩閫変竴锛夛細
  - apple_sleep_score(0鈥?00)锛屾垨
  - sleep_duration_hours + sleep_efficiency(0..1 鎴?0..100)
- 鎭㈠鎬э細restorative_ratio(0..1)
- HRV锛歨rv_trend(rising|stable|slight_decline|significant_decline)锛堝彲绌猴級
- Hooper(1..7)锛歠atigue_hooper, soreness_hooper, stress_hooper, sleep_hooper
- 鍏朵粬锛歯utrition(adequate|inadequate_mild|inadequate_moderate|inadequate_severe), gi_symptoms(none|mild|severe)
- 甯冨皵锛歛lcohol_consumed, late_caffeine, screen_before_bed, late_meal, is_sick, is_injured锛堢己鐪?false锛?- 绌哄€硷細鍏佽绌轰覆/None/NULL/NA/NaN锛岃缁冩椂鎸夌己澶卞鐞嗭紝涓嶈鍏ユ牱鏈?
蹇€熶娇鐢紙鍛戒护琛岋級
- CSV 鈫?CPT JSON锛?  - python 涓€у寲CPT/personalize_cpt.py --csv 个性化CPT/history_60d_backend.csv --user u001 --out 涓€у寲CPT/personalized_emission_cpt_u001.json --shrink-k 100
- 鍙€夐澶勭悊锛?  - python 
浠庢暟鎹簱鐩存帴璁粌锛堢ず渚嬶級
- 浠呯ず鎰忥細鎶婃煡璇㈢粨鏋滆浆涓?DataFrame 鍚庤皟鐢ㄨ缁冨嚱鏁板嵆鍙€?
杈撳嚭鏍煎紡锛圕PT JSON锛?- 缁撴瀯锛歿 evidence_type: { category: { state: prob } } }
- 浠呭寘鍚?EMISSION_CPT銆傚缓璁灞傚瓨鍌ㄦ椂鍔?meta锛坲ser_id, trained_at, days_used, shrink_k, used_vars 绛夛級銆?
閮ㄧ讲涓庨泦鎴愬缓璁?- 瀹氭椂浣滀笟锛氭瘡鏃?姣忓懆鎷夊彇婊¤冻 鈮?0 澶╃殑鐢ㄦ埛鍘嗗彶锛岃皟鐢ㄤ釜鎬у寲璁粌锛屼骇鍑?CPT JSON銆?- 瀛樺偍锛氱増鏈寲淇濆瓨锛圖B 琛ㄦ垨瀵硅薄瀛樺偍锛夛紝璁板綍 trained_at 涓庡弬鏁帮紝渚夸簬鍥炴粴涓庡璁°€?- 搴旂敤锛?  - 鏈湴婕旂ず锛歱ython 涓€у寲CPT/apply_cpt.py 涓€у寲CPT/personalized_emission_cpt_u001.json
  - 鏈嶅姟渚х儹鏇挎崲锛氳绠楁湇鍔″鐞嗚姹傚墠灏濊瘯鎸?user_id 鍔犺浇鐢ㄦ埛涓€у寲 CPT锛涙棤鍒欏洖閫€榛樿銆?
FAQ
- 鑻规灉鍒嗕笌浼犵粺鐫＄湢鑳藉悓鏃朵笂鎶ュ悧锛?  - 鍙互锛屼絾璁粌涓庢槧灏勯噰鐢ㄢ€滆嫻鏋滀紭鍏堚€濓紝浼犵粺 sleep_performance 灏嗚蹇界暐锛涘缓璁暟鎹眰鎸変簩閫変竴杈撳嚭銆?- 鑻规灉鍒嗕笉鍙敤鎬庝箞鍔烇紵
  - 鑷姩 fallback 鍒颁紶缁?sleep_performance锛堢敱鏃堕暱+鏁堢巼鏄犲皠锛夈€?- 鎭㈠鎬х潯鐪犳槸鍚﹁繕闇€瑕侊紵
  - 闇€瑕併€傝嫻鏋滃垎涓嶅寘鍚繁鐫?REM 淇℃伅锛宺estorative_sleep 浠嶇嫭绔嬪弬涓庡苟鍙釜鎬у寲銆?- 涓€у寲浠€涔堟椂鍊欑敓鏁堬紵
  - 鈮?0 澶╂墠杩涜涓€у寲锛涗笖姣忎釜璇佹嵁鐙珛 鈮?0 鏍锋湰鎵嶆洿鏂拌琛ㄣ€?

