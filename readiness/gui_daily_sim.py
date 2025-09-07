#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from readiness.service import compute_readiness_from_payload
from readiness.constants import TRAINING_LOAD_CPT


DATE_FMT = "%Y-%m-%d"


def nearest_training_key(label: str) -> str:
    keys = list(TRAINING_LOAD_CPT.keys())
    if label in keys:
        return label
    # 兼容键名存在编码差异的情况
    if label == '极高':
        for k in keys:
            if '极高' in k:
                return k
        return keys[0]
    if label == '高':
        cand = [k for k in keys if ('高' in k and '极' not in k)]
        if cand:
            # 选更重的那个
            from readiness.simulate_days_via_service import heaviness_score

            cand = sorted(cand, key=lambda k: heaviness_score(TRAINING_LOAD_CPT[k]), reverse=True)
            return cand[0]
        return keys[min(1, len(keys) - 1)] if len(keys) > 1 else keys[0]
    if label == '中':
        for k in keys:
            if '中' in k:
                return k
        return keys[len(keys) // 2]
    if label == '低':
        for k in keys:
            if '低' in k:
                return k
        return keys[-1]
    if label == '无':
        for k in keys:
            if '无' in k or '休' in k:
                return k
        return keys[-1]
    return keys[-1]


class DailySimApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("就绪度日更模拟器 (Readiness Daily Simulator)")

        # State across days
        self.prev_probs: Optional[Dict[str, float]] = None
        self.recent_loads: List[str] = []
        self.last_short_term: Dict[str, bool] = {
            'alcohol_consumed': False,
            'late_caffeine': False,
            'screen_before_bed': False,
            'late_meal': False,
        }

        # Top: Date/User/Gender
        frm_top = ttk.Frame(root)
        frm_top.pack(fill='x', padx=8, pady=6)
        ttk.Label(frm_top, text="日期 (YYYY-MM-DD)").grid(row=0, column=0, sticky='w')
        self.var_date = tk.StringVar(value=datetime.now().strftime(DATE_FMT))
        ttk.Entry(frm_top, textvariable=self.var_date, width=14).grid(row=0, column=1, padx=6)
        ttk.Label(frm_top, text="用户ID").grid(row=0, column=2, sticky='w')
        self.var_user = tk.StringVar(value='u_gui')
        ttk.Entry(frm_top, textvariable=self.var_user, width=10).grid(row=0, column=3, padx=6)
        ttk.Label(frm_top, text="性别").grid(row=0, column=4, sticky='w')
        self.var_gender = tk.StringVar(value='男')
        ttk.Combobox(frm_top, textvariable=self.var_gender, values=['男', '女'], width=5, state='readonly').grid(row=0, column=5, padx=6)

        # Training + Objective
        frm_mid = ttk.Frame(root)
        frm_mid.pack(fill='x', padx=8, pady=6)
        ttk.Label(frm_mid, text="训练负荷").grid(row=0, column=0, sticky='w')
        self.var_tload = tk.StringVar(value='中')
        ttk.Combobox(frm_mid, textvariable=self.var_tload, values=['极高', '高', '中', '低', '无'], width=8, state='readonly').grid(row=0, column=1, padx=6)

        ttk.Label(frm_mid, text="睡眠表现").grid(row=0, column=2, sticky='w')
        self.var_sleep_perf = tk.StringVar(value='medium')
        ttk.Combobox(frm_mid, textvariable=self.var_sleep_perf, values=['good', 'medium', 'poor'], width=8, state='readonly').grid(row=0, column=3, padx=6)

        ttk.Label(frm_mid, text="恢复性睡眠").grid(row=0, column=4, sticky='w')
        self.var_rest = tk.StringVar(value='medium')
        ttk.Combobox(frm_mid, textvariable=self.var_rest, values=['high', 'medium', 'low'], width=8, state='readonly').grid(row=0, column=5, padx=6)

        ttk.Label(frm_mid, text="HRV 趋势").grid(row=0, column=6, sticky='w')
        self.var_hrv = tk.StringVar(value='stable')
        ttk.Combobox(frm_mid, textvariable=self.var_hrv, values=['rising', 'stable', 'slight_decline', 'significant_decline'], width=18, state='readonly').grid(row=0, column=7, padx=6)

        # Hooper 1..7
        frm_h = ttk.LabelFrame(root, text="Hooper 主观评分 (1..7，数值越大越差)")
        frm_h.pack(fill='x', padx=8, pady=6)
        self.var_h_fatigue = tk.IntVar(value=3)
        self.var_h_soreness = tk.IntVar(value=3)
        self.var_h_stress = tk.IntVar(value=3)
        self.var_h_sleep = tk.IntVar(value=3)
        self._add_spin(frm_h, "疲劳 fatigue", self.var_h_fatigue, 0)
        self._add_spin(frm_h, "酸痛 soreness", self.var_h_soreness, 1)
        self._add_spin(frm_h, "压力 stress", self.var_h_stress, 2)
        self._add_spin(frm_h, "睡眠主观 sleep", self.var_h_sleep, 3)

        # Journal
        frm_j = ttk.LabelFrame(root, text="Journal（短期行为→影响次日先验；持久状态→当日后验）")
        frm_j.pack(fill='x', padx=8, pady=6)
        # Short-term
        self.var_alcohol = tk.BooleanVar(value=False)
        self.var_caffeine = tk.BooleanVar(value=False)
        self.var_screen = tk.BooleanVar(value=False)
        self.var_late_meal = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_j, text='酒精 alcohol_consumed', variable=self.var_alcohol).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(frm_j, text='晚咖啡 late_caffeine', variable=self.var_caffeine).grid(row=0, column=1, sticky='w')
        ttk.Checkbutton(frm_j, text='睡前刷屏 screen_before_bed', variable=self.var_screen).grid(row=0, column=2, sticky='w')
        ttk.Checkbutton(frm_j, text='晚餐 late_meal', variable=self.var_late_meal).grid(row=0, column=3, sticky='w')
        # Persistent
        self.var_sick = tk.BooleanVar(value=False)
        self.var_injured = tk.BooleanVar(value=False)
        self.var_high_stress = tk.BooleanVar(value=False)
        self.var_meditation = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm_j, text='生病 is_sick', variable=self.var_sick).grid(row=1, column=0, sticky='w')
        ttk.Checkbutton(frm_j, text='受伤 is_injured', variable=self.var_injured).grid(row=1, column=1, sticky='w')
        ttk.Checkbutton(frm_j, text='重大压力事件 high_stress_event_today', variable=self.var_high_stress).grid(row=1, column=2, sticky='w')
        ttk.Checkbutton(frm_j, text='冥想 meditation_done_today', variable=self.var_meditation).grid(row=1, column=3, sticky='w')

        # Cycle (optional)
        frm_cyc = ttk.LabelFrame(root, text="月经周期（可选：仅当性别=女时考虑）")
        frm_cyc.pack(fill='x', padx=8, pady=6)
        ttk.Label(frm_cyc, text='cycle day').grid(row=0, column=0, sticky='w')
        self.var_cycle_day = tk.StringVar(value='')
        ttk.Entry(frm_cyc, textvariable=self.var_cycle_day, width=6).grid(row=0, column=1, padx=6)
        ttk.Label(frm_cyc, text='cycle length').grid(row=0, column=2, sticky='w')
        self.var_cycle_len = tk.StringVar(value='')
        ttk.Entry(frm_cyc, textvariable=self.var_cycle_len, width=6).grid(row=0, column=3, padx=6)

        # Actions
        frm_btn = ttk.Frame(root)
        frm_btn.pack(fill='x', padx=8, pady=6)
        ttk.Button(frm_btn, text='计算今日 Compute', command=self.compute_today).pack(side='left')
        ttk.Button(frm_btn, text='下一天 Next Day', command=self.next_day).pack(side='left', padx=10)
        ttk.Button(frm_btn, text='清空短期行为', command=self.clear_short_term).pack(side='left')

        # Output
        frm_out = ttk.LabelFrame(root, text='输出 Output')
        frm_out.pack(fill='both', expand=True, padx=8, pady=6)
        self.txt = tk.Text(frm_out, height=12)
        self.txt.pack(fill='both', expand=True)

    def _add_spin(self, parent: tk.Widget, label: str, var: tk.IntVar, col: int) -> None:
        f = ttk.Frame(parent)
        f.grid(row=0, column=col, padx=8, pady=4)
        ttk.Label(f, text=label).pack(anchor='w')
        sb = ttk.Spinbox(f, from_=1, to=7, width=5, textvariable=var)
        sb.pack(anchor='w')

    def _build_payload(self) -> Dict[str, Any]:
        date = self.var_date.get().strip() or datetime.now().strftime(DATE_FMT)
        user = self.var_user.get().strip() or 'u_gui'
        gender = self.var_gender.get()
        tload_label = self.var_tload.get()
        tload_key = nearest_training_key(tload_label)

        # Journal (统一入口): 短期→影响今天（写入昨天仓库）；持久→影响今日（写入今日仓库）
        journal = {
            'alcohol_consumed': bool(self.var_alcohol.get()),
            'late_caffeine': bool(self.var_caffeine.get()),
            'screen_before_bed': bool(self.var_screen.get()),
            'late_meal': bool(self.var_late_meal.get()),
            'is_sick': bool(self.var_sick.get()),
            'is_injured': bool(self.var_injured.get()),
            'high_stress_event_today': bool(self.var_high_stress.get()),
            'meditation_done_today': bool(self.var_meditation.get()),
        }

        hooper = {
            'fatigue': int(self.var_h_fatigue.get()),
            'soreness': int(self.var_h_soreness.get()),
            'stress': int(self.var_h_stress.get()),
            'sleep': int(self.var_h_sleep.get()),
        }

        objective = {
            'sleep_performance_state': self.var_sleep_perf.get(),
            'restorative_sleep': self.var_rest.get(),
            'hrv_trend': self.var_hrv.get(),
        }

        cycle: Dict[str, Any] = {}
        if self.var_cycle_day.get().strip():
            try:
                cycle['day'] = int(self.var_cycle_day.get().strip())
            except Exception:
                pass
        if self.var_cycle_len.get().strip():
            try:
                cycle['cycle_length'] = int(self.var_cycle_len.get().strip())
            except Exception:
                pass

        payload: Dict[str, Any] = {
            'user_id': user,
            'date': date,
            'gender': gender,
            'previous_state_probs': self.prev_probs,
            'training_load': tload_key,
            'recent_training_loads': list(self.recent_loads[-8:]),
            'journal': journal,
            'objective': objective,
            'hooper': hooper,
        }
        if gender == '女' and cycle:
            payload['cycle'] = cycle
        return payload

    def compute_today(self) -> None:
        try:
            payload = self._build_payload()
            res = compute_readiness_from_payload(payload)
        except Exception as e:
            messagebox.showerror("错误", f"计算失败: {e}")
            return

        self.prev_probs = res.get('next_previous_state_probs')
        # 记录本日短期行为，留到“下一天”作为默认值
        self.last_short_term = {
            'alcohol_consumed': bool(self.var_alcohol.get()),
            'late_caffeine': bool(self.var_caffeine.get()),
            'screen_before_bed': bool(self.var_screen.get()),
            'late_meal': bool(self.var_late_meal.get()),
        }
        # recent loads 滚动
        self.recent_loads.append(self.var_tload.get())

        score = res.get('final_readiness_score')
        dx = res.get('final_diagnosis')
        prior = res.get('prior_probs') or {}
        post = res.get('final_posterior_probs') or {}

        # 展示
        self.txt.delete('1.0', tk.END)
        self.txt.insert(tk.END, f"日期: {payload['date']}  用户: {payload['user_id']}  性别: {payload['gender']}\n")
        self.txt.insert(tk.END, f"训练负荷: {self.var_tload.get()}  Hooper: f{self.var_h_fatigue.get()}, s{self.var_h_soreness.get()}, st{self.var_h_stress.get()}, sl{self.var_h_sleep.get()}\n")
        self.txt.insert(tk.END, f"客观: sleep={self.var_sleep_perf.get()} rest={self.var_rest.get()} hrv={self.var_hrv.get()}\n")
        self.txt.insert(tk.END, f"Journal短期: A={int(self.var_alcohol.get())} C={int(self.var_caffeine.get())} S={int(self.var_screen.get())} M={int(self.var_late_meal.get())}\n")
        self.txt.insert(tk.END, f"Journal持久: sick={int(self.var_sick.get())} inj={int(self.var_injured.get())} high_stress={int(self.var_high_stress.get())} meditation={int(self.var_meditation.get())}\n\n")
        self.txt.insert(tk.END, f"Readiness: {score}  诊断: {dx}\n\n")
        self.txt.insert(tk.END, "先验 Prior:\n")
        for k, v in prior.items():
            self.txt.insert(tk.END, f"  {k}: {v:.3f}\n")
        self.txt.insert(tk.END, "\n后验 Posterior:\n")
        for k, v in post.items():
            self.txt.insert(tk.END, f"  {k}: {v:.3f}\n")

    def next_day(self) -> None:
        # 日期 +1
        try:
            d = datetime.strptime(self.var_date.get().strip(), DATE_FMT)
        except Exception:
            d = datetime.now()
        d2 = d + timedelta(days=1)
        self.var_date.set(d2.strftime(DATE_FMT))

        # 将“上一日”的短期行为作为默认，方便“真实部署”的体验
        self.var_alcohol.set(self.last_short_term.get('alcohol_consumed', False))
        self.var_caffeine.set(self.last_short_term.get('late_caffeine', False))
        self.var_screen.set(self.last_short_term.get('screen_before_bed', False))
        self.var_late_meal.set(self.last_short_term.get('late_meal', False))

        # 持久状态默认清空，避免误延续
        self.var_sick.set(False)
        self.var_injured.set(False)
        self.var_high_stress.set(False)
        self.var_meditation.set(False)

        self.txt.insert(tk.END, f"\n—— 已进入下一天: {self.var_date.get()} ——\n")

    def clear_short_term(self) -> None:
        self.var_alcohol.set(False)
        self.var_caffeine.set(False)
        self.var_screen.set(False)
        self.var_late_meal.set(False)


def main() -> None:
    root = tk.Tk()
    DailySimApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

