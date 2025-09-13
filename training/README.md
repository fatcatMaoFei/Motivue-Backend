Training Consumption锛堝綋鏃ヨ缁冩秷鑰楀垎锛?
鐩殑
- 鐙珛璁＄畻鈥滃綋鏃ユ秷鑰楀垎鈥濓紝鐢ㄤ簬鍓嶇鏄剧ず鈥滃綋鍓嶅墿浣欏噯澶囧害 = 鍑嗗搴?鈭?褰撴棩娑堣€椻€濄€?- 涓嶆敼鍙?readiness 鐨勫綋澶╁悗楠屼笌鍒嗘暟锛屼粎渚涘睍绀恒€?
榛樿瑙勫垯锛坴1锛?- 浠呰缁冨洜瀛愶紝RPE脳鍒嗛挓涓轰富锛沴abel 涓哄厹搴曪紱涔熸帴鍙椾紶鍏?au锛堟渶鍚庡厹搴曪級銆?- 鍗曟璁粌鏈€澶ф秷鑰?cap_session = 40锛涘綋鏃ヨ缁冩€绘秷鑰?cap_training_total = 60銆?- 娑堣€楁洸绾?g(AU)锛?  - AU 鈮?150 鈫?0
  - 150..300 鈫?0..10锛堢嚎鎬э級
  - 300..500 鈫?10..25锛堢嚎鎬э級
  - >500 鈫?25..40锛堢嚎鎬ц嚦 900 楗卞拰锛?- readiness 鏀惧ぇ绯绘暟 scale(R) 棰勭暀锛寁1 鍥哄畾 1.0锛堜笉闅?R 鍙樺寲锛夈€?
鐩綍
- training/consumption.py        缁熶竴鍏ュ彛锛坈alculate_consumption锛?- training/factors/training.py   璁粌鍥犲瓙瀹炵幇锛圧PE 涓轰富锛?- training/schemas.py            杈撳叆/杈撳嚭缁撴瀯

鎺ュ彛
- calculate_consumption(payload: TrainingConsumptionInput) -> TrainingConsumptionOutput
- 杈撳叆锛堝叧閿瓧娈碉級
  - user_id: str
  - date: YYYY-MM-DD
  - base_readiness_score: int锛堝彲閫夛紱鑻ユ彁渚涘皢椤烘墜杩斿洖 display_readiness锛?  - training_sessions: list[{
      rpe: int 1..10,
      duration_minutes: int,
      label: "鏋侀珮"|"楂?|"涓?|"浣?|"浼戞伅"锛堝彲閫夛級锛?      au: float锛堝彲閫夛級锛?      session_id/start_time: 鍙€?    }]
  - params_override: dict锛堝彲閫夛細cap_session銆乧ap_training_total銆佹洸绾垮弬鏁扮瓑鏈潵鎷撳睍锛?- 杈撳嚭
  - consumption_score: float锛堝綋鏃ヨ缁冩€绘秷鑰楋級
  - display_readiness: int = max(0, base_readiness_score - round(consumption_score))锛堣嫢浼犱簡 base锛?  - breakdown: {"training": number}
  - sessions: [{session_id, au_used, label_used, delta_consumption}]
  - caps_applied: {cap_session, cap_training_total}
  - params_used: dict锛堝璁★級

绀轰緥锛圥ython锛?```python
from training import calculate_consumption

payload = {
  "user_id": "u001",
  "date": "2025-09-12",
  "base_readiness_score": 80,
  "training_sessions": [
    {"rpe": 8, "duration_minutes": 60},
    {"label": "涓?, "duration_minutes": 30},
  ]
}
res = calculate_consumption(payload)
# res = {"consumption_score": 22.5, "display_readiness": 57, ...}
```

鍓嶇鐢ㄦ硶
- 鍒濆锛氭秷鑰?0 鈫?鏄剧ず=鍑嗗搴?- 鏍囪璁粌锛氳皟鐢?calculate_consumption锛屽埛鏂扳€滃綋鍓嶅墿浣欏噯澶囧害鈥?- 澶氭璁粌锛氬彔鍔狅紙鍙?cap_training_total 闄愬埗锛?
鎵╁睍
- 棰勭暀 journal 涓?device_metrics 瀛楁锛屾湭鏉ュ彲鎺ュ叆 alcohol/steps 绛夋柊鍥犲瓙锛?- 鍥犲瓙鏋舵瀯锛歵raining/factors/ 涓嬫柊澧炲洜瀛愶紝骞跺湪 consumption 涓仛鍚堟眰鍜岋紝鍐嶅鏃ユ€讳笂闄愶紙cap_day_total锛屽悗缁柊澧烇級銆?

