#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

# Allow running this file directly (python readiness/gui_daily_sim.py)
# by adding the project root to sys.path so that `import readiness.*` works.
import os, sys
_this_dir = os.path.dirname(__file__)
_proj_root = os.path.abspath(os.path.join(_this_dir, os.pardir))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from readiness.service import compute_readiness_from_payload
from readiness.constants import TRAINING_LOAD_CPT, TRAINING_LOAD_AU


DATE_FMT = "%Y-%m-%d"


def normalize_training_label(label: str) -> str:
    """Normalize to one of ['极高','高','中','低','无']."""
    keys = list(TRAINING_LOAD_CPT.keys())
    if label in keys:
        return label
    if not isinstance(label, str):
        return '中' if '中' in keys else (keys[len(keys)//2] if keys else '')
    if '极高' in label:
        return '极高' if '极高' in keys else (keys[0] if keys else '')
    if '高' in label and '极' not in label:
        return '高' if '高' in keys else (keys[min(1, len(keys)-1)] if keys else '')
    if '中' in label:
        return '中' if '中' in keys else (keys[len(keys)//2] if keys else '')
    if '低' in label:
        return '低' if '低' in keys else (keys[-2] if len(keys) >= 2 else (keys[-1] if keys else ''))
    if '无' in label or '休' in label:
        return '无' if '无' in keys else (keys[-1] if keys else '')
    return '中' if '中' in keys else (keys[len(keys)//2] if keys else '')


class DailySimApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("就绪度日更模拟器 (Readiness Daily Simulator)")

        # State across days
        self.prev_probs: Optional[Dict[str, float]] = None
        self.recent_loads: List[str] = []
        self.recent_au: List[float] = []
        self._today_au_value: float = 0.0
        self.session_rows: List[Dict[str, Any]] = []  # for CSV export
        self.last_short_term: Dict[str, bool] = {
            'alcohol_consumed': False,
            'late_caffeine': False,
            'screen_before_bed': False,
            'late_meal': False,
        }
        self.pending_short_term: Dict[str, bool] = {k: False for k in self.last_short_term}

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

        # Training input mode (Label vs RPE×Duration)
        frm_mode = ttk.Frame(root)
        frm_mode.pack(fill='x', padx=8, pady=4)
        ttk.Label(frm_mode, text='训练输入模式').pack(side='left')
        self.var_mode = tk.StringVar(value='label')
        ttk.Radiobutton(frm_mode, text='标签 Label', variable=self.var_mode, value='label', command=self._update_training_mode_ui).pack(side='left', padx=6)
        ttk.Radiobutton(frm_mode, text='RPE×时长', variable=self.var_mode, value='rpe', command=self._update_training_mode_ui).pack(side='left')

        # Training + Objective
        frm_mid = ttk.Frame(root)
        frm_mid.pack(fill='x', padx=8, pady=6)
        self.lbl_tload = ttk.Label(frm_mid, text="训练负荷")
        self.lbl_tload.grid(row=0, column=0, sticky='w')
        self.var_tload = tk.StringVar(value='中')
        self.combo_tload = ttk.Combobox(frm_mid, textvariable=self.var_tload, values=['极高', '高', '中', '低', '无'], width=8, state='readonly')
        self.combo_tload.grid(row=0, column=1, padx=6)

        ttk.Label(frm_mid, text="睡眠表现").grid(row=0, column=2, sticky='w')
        self.var_sleep_perf = tk.StringVar(value='medium')
        ttk.Combobox(frm_mid, textvariable=self.var_sleep_perf, values=['good', 'medium', 'poor'], width=8, state='readonly').grid(row=0, column=3, padx=6)

        ttk.Label(frm_mid, text="恢复性睡眠").grid(row=0, column=4, sticky='w')
        self.var_rest = tk.StringVar(value='medium')
        ttk.Combobox(frm_mid, textvariable=self.var_rest, values=['high', 'medium', 'low'], width=8, state='readonly').grid(row=0, column=5, padx=6)

        ttk.Label(frm_mid, text="HRV 趋势").grid(row=0, column=6, sticky='w')
        self.var_hrv = tk.StringVar(value='stable')
        ttk.Combobox(frm_mid, textvariable=self.var_hrv, values=['rising', 'stable', 'slight_decline', 'significant_decline'], width=18, state='readonly').grid(row=0, column=7, padx=6)

        # RPE×Duration row (separate frame; shown only when mode=rpe)
        self.frm_rpe = ttk.Frame(root)
        self.frm_rpe.pack(fill='x', padx=8, pady=4)
        ttk.Label(self.frm_rpe, text='RPE (1..10)').grid(row=0, column=0, sticky='w')
        self.var_rpe = tk.IntVar(value=5)
        ttk.Spinbox(self.frm_rpe, from_=1, to=10, textvariable=self.var_rpe, width=6).grid(row=0, column=1, padx=6)
        ttk.Label(self.frm_rpe, text='时长 min').grid(row=0, column=2, sticky='w')
        self.var_duration = tk.IntVar(value=60)
        ttk.Spinbox(self.frm_rpe, from_=0, to=600, textvariable=self.var_duration, width=8).grid(row=0, column=3, padx=6)
        # Initialize UI state
        self._update_training_mode_ui()

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
        frm_j = ttk.LabelFrame(root, text="Journal（短期→影响今日先验；持久→影响当日后验）")
        frm_j.pack(fill='x', padx=8, pady=6)
        self.var_st_when = tk.StringVar(value='yesterday')
        ttk.Radiobutton(frm_j, text='昨晚/yesterday', variable=self.var_st_when, value='yesterday').grid(row=0, column=0, sticky='w')
        ttk.Radiobutton(frm_j, text='今晚/tonight', variable=self.var_st_when, value='tonight').grid(row=0, column=1, sticky='w')

        self.var_alcohol = tk.BooleanVar(value=False)
        self.var_caffeine = tk.BooleanVar(value=False)
        self.var_screen = tk.BooleanVar(value=False)
        self.var_late_meal = tk.BooleanVar(value=False)
        self.var_sick = tk.BooleanVar(value=False)
        self.var_injured = tk.BooleanVar(value=False)
        self.var_high_stress = tk.BooleanVar(value=False)
        self.var_meditation = tk.BooleanVar(value=False)

        checks = [
            ("酒精 alcohol", self.var_alcohol),
            ("晚咖啡因 late caffeine", self.var_caffeine),
            ("睡前屏幕 screen", self.var_screen),
            ("夜宵 late meal", self.var_late_meal),
            ("生病 sick", self.var_sick),
            ("受伤 injured", self.var_injured),
            ("当天强压 high stress", self.var_high_stress),
            ("冥想 meditation", self.var_meditation),
        ]
        for i, (label, var) in enumerate(checks):
            ttk.Checkbutton(frm_j, text=label, variable=var).grid(row=1 + i // 4, column=i % 4, sticky='w', padx=6)

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
        ttk.Button(frm_btn, text='导出CSV Export', command=self.export_csv).pack(side='left', padx=10)

        # Output
        frm_out = ttk.LabelFrame(root, text='输出 Output')
        frm_out.pack(fill='both', expand=True, padx=8, pady=6)
        self.txt = tk.Text(frm_out, height=12)
        self.txt.pack(fill='both', expand=True)

        # Custom Journal JSON (persist only, not used in computation)
        frm_custom = ttk.LabelFrame(root, text='自定义 Journal（JSON；仅持久化，不参与当天计算）')
        frm_custom.pack(fill='x', padx=8, pady=6)
        self.var_custom_journal = tk.Text(frm_custom, height=3)
        self.var_custom_journal.pack(fill='x')

    def _add_spin(self, parent: tk.Widget, label: str, var: tk.IntVar, col: int) -> None:
        f = ttk.Frame(parent)
        f.grid(row=0, column=col, padx=8, pady=4)
        ttk.Label(f, text=label).pack(anchor='w')
        sb = ttk.Spinbox(f, from_=1, to=7, width=5, textvariable=var)
        sb.pack(anchor='w')

    def _update_training_mode_ui(self) -> None:
        mode = self.var_mode.get() if hasattr(self, 'var_mode') else 'label'
        if mode == 'rpe':
            # Hide label controls, show RPE frame
            try:
                self.lbl_tload.grid_remove()
                self.combo_tload.grid_remove()
            except Exception:
                pass
            try:
                self.frm_rpe.pack_configure(fill='x', padx=8, pady=4)
            except Exception:
                pass
        else:
            # Show label controls, hide RPE frame
            try:
                self.lbl_tload.grid(row=0, column=0, sticky='w')
                self.combo_tload.grid(row=0, column=1, padx=6)
            except Exception:
                pass
            try:
                self.frm_rpe.pack_forget()
            except Exception:
                pass

    def _build_payload(self) -> Dict[str, Any]:
        date = self.var_date.get().strip() or datetime.now().strftime(DATE_FMT)
        user = self.var_user.get().strip() or 'u_gui'
        gender_raw = self.var_gender.get()
        tload_label = self.var_tload.get()
        tload_key = normalize_training_label(tload_label)

        # Compute today's AU based on mode
        mode = self.var_mode.get()
        if mode == 'rpe':
            try:
                rpe = int(self.var_rpe.get())
                dur = int(self.var_duration.get())
                au_today = max(0, rpe) * max(0, dur)
            except Exception:
                au_today = 0
            # Map AU -> label for prior
            def au_to_label(au: float) -> str:
                # boundaries based on midpoints between constants
                # None/Low:100, Low/Med:275, Med/High:425, High/VeryHigh:600
                if au < 100: return '无'
                if au < 275: return '低'
                if au < 425: return '中'
                if au < 600: return '高'
                return '极高'
            tload_key = au_to_label(float(au_today))
            # Keep UI label value in sync for logs/CSV and recent_loads
            self.var_tload.set(tload_key)
        else:
            # Label mode -> derive AU from mapping for ACWR buffer
            au_today = float(TRAINING_LOAD_AU.get(tload_key, 0))

        # Stash for use after compute
        self._today_au_value = float(au_today)

        # Journal (统一入口)
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
        # If user marks as "tonight", do not apply short-term to today; defer to next day
        if self.var_st_when.get() == 'tonight':
            self.pending_short_term = {
                'alcohol_consumed': journal['alcohol_consumed'],
                'late_caffeine': journal['late_caffeine'],
                'screen_before_bed': journal['screen_before_bed'],
                'late_meal': journal['late_meal'],
            }
            journal['alcohol_consumed'] = False
            journal['late_caffeine'] = False
            journal['screen_before_bed'] = False
            journal['late_meal'] = False

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

        # Custom journal: allow JSON dict; if plain text, split by commas into {token: True}
        whoop_journal: Optional[Dict[str, Any]] = None
        custom_to_merge: Dict[str, Any] = {}
        txt = self.var_custom_journal.get('1.0', 'end').strip()
        if txt:
            try:
                import json
                j = json.loads(txt)
                if isinstance(j, dict):
                    whoop_journal = j
                    custom_to_merge = dict(j)
            except Exception:
                # Fallback: split by commas (including Chinese comma)
                parts = [p.strip() for p in txt.replace('，', ',').split(',') if p.strip()]
                if parts:
                    custom_to_merge = {p: True for p in parts}
                    whoop_journal = dict(custom_to_merge)

        # Normalize gender string for computation
        gender = '女' if gender_raw in ('女', '女性') else '男'

        # Normalize gender string for computation
        gender = '女' if gender_raw in ('女', '女性') else '男'

        # Build recent AU including today for ACWR
        recent_au_for_payload = (self.recent_au[-27:] + [float(self._today_au_value)]) if self.recent_au else [float(self._today_au_value)]

        payload: Dict[str, Any] = {
            'user_id': user,
            'date': date,
            'gender': gender,
            'previous_state_probs': self.prev_probs,
            'training_load': tload_key,
            'recent_training_loads': list(self.recent_loads[-8:]),
            'recent_training_au': recent_au_for_payload,
            'journal': {**journal, **custom_to_merge} if custom_to_merge else journal,
            'objective': objective,
            'hooper': hooper,
        }
        if gender == '女' and cycle:
            payload['cycle'] = cycle
        if whoop_journal is not None:
            payload['whoop_journal'] = whoop_journal
        return payload

    def compute_today(self) -> None:
        try:
            payload = self._build_payload()
            res = compute_readiness_from_payload(payload)
        except Exception as e:
            messagebox.showerror("错误", f"计算失败: {e}")
            return

        self.prev_probs = res.get('next_previous_state_probs')
        # Update short-term for next day
        if self.var_st_when.get() == 'yesterday':
            self.last_short_term = {k: False for k in self.last_short_term}
        else:
            self.last_short_term = dict(self.pending_short_term)
        # recent buffers 滚动
        self.recent_loads.append(self.var_tload.get())
        self.recent_au.append(float(self._today_au_value))

        score = res.get('final_readiness_score')
        dx = res.get('final_diagnosis')
        prior = res.get('prior_probs') or {}
        post = res.get('final_posterior_probs') or {}

        # Training intensity score and ACWR (display only)
        try:
            from readiness.simulate_days_via_service import heaviness_score
            t_key = payload['training_load']
            intensity = float(heaviness_score(TRAINING_LOAD_CPT.get(t_key, {})))
        except Exception:
            intensity = 0.0
        # Use AU buffer for ACWR display
        au_series: List[float] = list(self.recent_au[-28:])
        A7 = C28 = R = None
        if len(au_series) >= 7:
            last7 = au_series[-7:]
            last28 = au_series[-28:] if len(au_series) >= 28 else list(au_series)
            A7 = sum(last7) / len(last7) if last7 else 0.0
            C28 = sum(last28) / len(last28) if last28 else 0.0
            R = (A7 / C28) if C28 and C28 > 0 else None

        # Show
        self.txt.delete('1.0', tk.END)
        self.txt.insert(tk.END, f"日期: {payload['date']}  用户: {payload['user_id']}  性别: {payload['gender']}\n")
        self.txt.insert(tk.END, f"训练负荷: {self.var_tload.get()}  Hooper: f{self.var_h_fatigue.get()}, s{self.var_h_soreness.get()}, st{self.var_h_stress.get()}, sl{self.var_h_sleep.get()}\n")
        self.txt.insert(tk.END, f"客观: sleep={self.var_sleep_perf.get()} rest={self.var_rest.get()} hrv={self.var_hrv.get()}  强度={intensity:.3f}  今日AU={self._today_au_value:.0f}\n")
        if R is not None:
            self.txt.insert(tk.END, f"ACWR: A7={A7:.1f} C28={C28:.1f} R7/28={R:.2f}\n")
        self.txt.insert(tk.END, f"Journal短期: A={int(self.var_alcohol.get())} C={int(self.var_caffeine.get())} S={int(self.var_screen.get())} M={int(self.var_late_meal.get())}\n")
        self.txt.insert(tk.END, f"Journal持久: sick={int(self.var_sick.get())} inj={int(self.var_injured.get())} high_stress={int(self.var_high_stress.get())} meditation={int(self.var_meditation.get())}\n\n")
        self.txt.insert(tk.END, f"Readiness: {score}  诊断: {dx}\n\n")
        self.txt.insert(tk.END, "先验 Prior:\n")
        for k, v in prior.items():
            self.txt.insert(tk.END, f"  {k}: {v:.3f}\n")
        self.txt.insert(tk.END, "\n后验 Posterior:\n")
        for k, v in post.items():
            self.txt.insert(tk.END, f"  {k}: {v:.3f}\n")

        # Save record for CSV export
        # Persist row (values in GUI native language; export step will map to English)
        row = {
            'date': payload['date'],
            'user_id': payload['user_id'],
            'gender': payload['gender'],
            'training_load_label': self.var_tload.get(),
            'training_load_key': payload['training_load'],
            'training_input_mode': self.var_mode.get(),
            'rpe': int(self.var_rpe.get()),
            'duration_min': int(self.var_duration.get()),
            'training_au_today': float(self._today_au_value),
            'training_intensity_score': intensity,
            'fatigue': self.var_h_fatigue.get(),
            'soreness': self.var_h_soreness.get(),
            'stress': self.var_h_stress.get(),
            'sleep': self.var_h_sleep.get(),
            'short_term_when': self.var_st_when.get(),
            'alcohol': int(self.var_alcohol.get()),
            'late_caffeine': int(self.var_caffeine.get()),
            'screen_before_bed': int(self.var_screen.get()),
            'late_meal': int(self.var_late_meal.get()),
            'is_sick': int(self.var_sick.get()),
            'is_injured': int(self.var_injured.get()),
            'high_stress_event_today': int(self.var_high_stress.get()),
            'meditation_done_today': int(self.var_meditation.get()),
            'sleep_perf': self.var_sleep_perf.get(),
            'restorative_sleep': self.var_rest.get(),
            'hrv_trend': self.var_hrv.get(),
            'cycle_day': self.var_cycle_day.get().strip(),
            'cycle_length': self.var_cycle_len.get().strip(),
            'custom_journal_json': self.var_custom_journal.get('1.0', 'end').strip(),
            'readiness_score': score,
            'diagnosis': dx,
        }
        self.session_rows.append(row)

    def next_day(self) -> None:
        # 日期 +1
        try:
            d = datetime.strptime(self.var_date.get().strip(), DATE_FMT)
        except Exception:
            d = datetime.now()
        d2 = d + timedelta(days=1)
        self.var_date.set(d2.strftime(DATE_FMT))

        # 将“今晚”的短期行为作为下一天默认（若选择了“今晚”）
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

    def export_csv(self) -> None:
        if not self.session_rows:
            messagebox.showinfo("提示", "暂无可导出的记录。请先计算至少一天。")
            return
        path = filedialog.asksaveasfilename(
            title='选择导出路径',
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv')],
            initialfile=f'session_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        if not path:
            return
        # Write CSV
        import csv
        fields = [
            'date','user_id','gender','training_load_label','training_load_key','training_input_mode','rpe','duration_min','training_au_today','training_intensity_score',
            'fatigue','soreness','stress','sleep',
            'short_term_when','alcohol','late_caffeine','screen_before_bed','late_meal',
            'is_sick','is_injured','high_stress_event_today','meditation_done_today',
            'sleep_perf','restorative_sleep','hrv_trend','cycle_day','cycle_length','custom_journal_json',
            'readiness_score','diagnosis'
        ]
        # English-only value mapping for export to avoid mojibake in Excel
        def to_en(val: Any) -> Any:
            if isinstance(val, str):
                if val in ('男','女'):
                    return 'male' if val == '男' else 'female'
                m = {'极高':'very_high','高':'high','中':'medium','低':'low','无':'none'}
                if val in m:
                    return m[val]
            return val
        try:
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                for r in self.session_rows:
                    out = {k: r.get(k, '') for k in fields}
                    out['gender'] = to_en(out.get('gender'))
                    out['training_load_label'] = to_en(out.get('training_load_label'))
                    out['training_load_key'] = to_en(out.get('training_load_key'))
                    w.writerow(out)
            messagebox.showinfo("完成", f"已导出 {len(self.session_rows)} 条记录到:\n{path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")


def main() -> None:
    root = tk.Tk()
    DailySimApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
