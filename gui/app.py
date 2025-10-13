#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

# Ensure we can import readiness from repo root
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from readiness.service import compute_readiness_from_payload
from readiness.constants import TRAINING_LOAD_AU


CSV_DEFAULT = os.path.join(ROOT, '个性化CPT', 'history_gui_log.csv')


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']

def init_state():
    if 'date' not in st.session_state:
        st.session_state.date = datetime.today().date()
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 'user_001'
    if 'gender' not in st.session_state:
        st.session_state.gender = '男性'
    if 'prev_probs' not in st.session_state:
        st.session_state.prev_probs = {
            'Peak': 0.2, 'Well-adapted': 0.4, 'FOR': 0.3,
            'Acute Fatigue': 0.1, 'NFOR': 0.0, 'OTS': 0.0
        }
    if 'short_term_pending' not in st.session_state:
        st.session_state.short_term_pending = {}
    if 'recent_training_au' not in st.session_state:
        st.session_state.recent_training_au: List[float] = []
    if 'nextday_training_label' not in st.session_state:
        st.session_state.nextday_training_label = None
    if 'csv_path' not in st.session_state:
        st.session_state.csv_path = CSV_DEFAULT
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None


def label_to_au(label: str) -> float:
    return float(TRAINING_LOAD_AU.get(label, 0))


def au_to_label_by_nearest(au: float) -> str:
    # Choose the nearest label based on TRAINING_LOAD_AU distances
    best_label, best_dist = None, None
    for lbl, val in TRAINING_LOAD_AU.items():
        d = abs(float(val) - au)
        if best_dist is None or d < best_dist:
            best_label, best_dist = lbl, d
    return best_label or '无'


def build_payload(today_inputs: Dict[str, Any]) -> Dict[str, Any]:
    date_str = today_inputs['date'].strftime('%Y-%m-%d')
    payload: Dict[str, Any] = {
        'user_id': today_inputs['user_id'],
        'date': date_str,
        'gender': today_inputs['gender'],
        'previous_state_probs': st.session_state.prev_probs,
    }

    # Training load (today prior)
    if today_inputs.get('training_load'):
        payload['training_load'] = today_inputs['training_load']

    # Sleep
    if today_inputs.get('apple_sleep_score') is not None:
        payload['apple_sleep_score'] = today_inputs['apple_sleep_score']
    if today_inputs.get('sleep_performance_state'):
        payload['sleep_performance_state'] = today_inputs['sleep_performance_state']
    if today_inputs.get('restorative_sleep'):
        payload['restorative_sleep'] = today_inputs['restorative_sleep']

    # HRV
    if today_inputs.get('hrv_trend'):
        payload['hrv_trend'] = today_inputs['hrv_trend']

    # Hooper
    hooper = {}
    for k in ['fatigue', 'soreness', 'stress', 'sleep']:
        v = today_inputs.get(f'{k}_hooper')
        if v is not None and 1 <= v <= 7:
            hooper[k] = int(v)
    if hooper:
        payload['hooper'] = hooper

    # Nutrition & GI
    if today_inputs.get('nutrition'):
        payload['nutrition'] = today_inputs['nutrition']
    if today_inputs.get('gi_symptoms'):
        payload['gi_symptoms'] = today_inputs['gi_symptoms']

    # Journal: persistent today (affects today posterior immediately)
    journal_today = {}
    for key in ['is_sick', 'is_injured', 'high_stress_event_today', 'meditation_done_today']:
        journal_today[key] = bool(today_inputs.get(key, False))
    payload['journal_today'] = journal_today

    # Female cycle (optional): affect today posterior
    if today_inputs.get('gender') == '濂虫€?:
        day = today_inputs.get('cycle_day')
        length = today_inputs.get('cycle_length')
        if day is not None and length is not None and day > 0 and length > 0:
            payload['cycle'] = {'day': int(day), 'length': int(length)}

    # Yesterday short-term (affects today prior): use pending from session
    if st.session_state.short_term_pending:
        payload['journal_yesterday'] = dict(st.session_state.short_term_pending)

    return payload


def append_csv(row: Dict[str, Any]):
    path = st.session_state.csv_path
    df = pd.DataFrame([row])
    header = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8')


def main():
    st.set_page_config(page_title='Readiness 鎵嬪伐褰曞叆涓庢祴璇?, layout='wide')
    init_state()

    st.sidebar.header('鍏ㄥ眬璁剧疆')
    st.session_state.csv_path = st.sidebar.text_input('CSV淇濆瓨璺緞', st.session_state.csv_path)

    colA, colB, colC = st.columns(3)
    with colA:
        st.session_state.user_id = st.text_input('鐢ㄦ埛ID', st.session_state.user_id)
        st.session_state.gender = st.selectbox('鎬у埆', ['鐢锋€?, '濂虫€?], index=0 if st.session_state.gender=='鐢锋€? else 1)
    with colB:
        st.session_state.date = st.date_input('鏃ユ湡', st.session_state.date)
    with colC:
        st.write('涓婁竴鏃ョ姸鎬佸垎甯?(棣栨棩鍙噸缃?')
        if st.button('閲嶇疆鍒濆鍒嗗竷', help='閲嶇疆涓?[0.2,0.4,0.3,0.1,0,0]'):
            st.session_state.prev_probs = {
                'Peak': 0.2, 'Well-adapted': 0.4, 'FOR': 0.3,
                'Acute Fatigue': 0.1, 'NFOR': 0.0, 'OTS': 0.0
            }
        st.json(st.session_state.prev_probs)

    st.markdown('---')
    st.subheader('璁粌寮哄害锛堢敤浜庢槑澶╁厛楠岋紱鏍囩涓哄噯锛岃褰昍PE脳鍒嗛挓AU锛?)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        training_load = st.selectbox('浠婃棩寮哄害鏍囩', ['鏋侀珮','楂?,'涓?,'浣?,'浼戞伅'])
    with c2:
        rpe = st.number_input('RPE(1..10)', min_value=0, max_value=10, value=0, step=1)
    with c3:
        duration_min = st.number_input('璁粌鏃堕暱(鍒嗛挓)', min_value=0, max_value=1000, value=0, step=10)
    with c4:
        st.write('璇存槑锛氭爣绛剧敤浜庝粖鏃ュ厛楠岋紱RPE脳鍒嗛挓鐢ㄤ簬鏄庡ぉAU搴忓垪銆?)

    rpe_au = int(rpe * duration_min) if (rpe and duration_min) else 0
    label_au = int(label_to_au(training_load))
    inferred_label_from_rpe = au_to_label_by_nearest(rpe_au) if rpe_au>0 else None
    conflict = 1 if (inferred_label_from_rpe and inferred_label_from_rpe != training_load) else 0
    st.caption(f'RPE脳鍒嗛挓 AU={rpe_au}锛涙爣绛続U={label_au}锛汻PE鈫掓爣绛?{inferred_label_from_rpe or "N/A"}锛涘啿绐?{bool(conflict)}')

    st.markdown('---')
    st.subheader('鐫＄湢涓嶩RV锛堜粖澶╁悗楠岋級')
    c5, c6, c7 = st.columns(3)
    with c5:
        apple_sleep_score = st.number_input('鑻规灉鐫＄湢鍒?0-100)', min_value=0, max_value=100, value=0, step=1)
        sleep_perf = st.selectbox('浼犵粺鐫＄湢琛ㄧ幇', ['(涓嶅～)','good','medium','poor'], index=0)
    with c6:
        restorative_sleep = st.selectbox('鎭㈠鎬х潯鐪?, ['(涓嶅～)','high','medium','low'], index=0)
        hrv_trend = st.selectbox('HRV瓒嬪娍', ['(涓嶅～)','rising','stable','slight_decline','significant_decline'], index=0)
    with c7:
        gender = st.session_state.gender
        cycle_day = st.number_input('鍛ㄦ湡鏃?day)', min_value=0, max_value=60, value=0, step=1)
        cycle_length = st.number_input('鍛ㄦ湡闀垮害(length)', min_value=0, max_value=60, value=0, step=1)

    st.markdown('---')
    st.subheader('Hooper锛?..7锛変笌鍏跺畠锛堜粖澶╁悗楠岋級')
    c8, c9, c10, c11 = st.columns(4)
    with c8:
        fatigue_hooper = st.number_input('鐤插姵 Hooper', min_value=0, max_value=7, value=0, step=1)
    with c9:
        soreness_hooper = st.number_input('閰哥棝 Hooper', min_value=0, max_value=7, value=0, step=1)
    with c10:
        stress_hooper = st.number_input('鍘嬪姏 Hooper', min_value=0, max_value=7, value=0, step=1)
    with c11:
        sleep_hooper = st.number_input('鐫＄湢 Hooper', min_value=0, max_value=7, value=0, step=1)

    c12, c13 = st.columns(2)
    with c12:
        nutrition = st.selectbox('钀ュ吇', ['(涓嶅～)','adequate','inadequate_mild','inadequate_moderate','inadequate_severe'], index=0)
    with c13:
        gi_symptoms = st.selectbox('GI鐥囩姸', ['(涓嶅～)','none','mild','severe'], index=0)

    st.markdown('---')
    st.subheader('Journal 鍕鹃€夛紙鐭湡鈫掓槑澶╁厛楠岋紱褰撴棩鈫掍粖澶╁悗楠岋級')
    c14, c15 = st.columns(2)
    with c14:
        alcohol = st.checkbox('鏄ㄦ櫄楗厭 (褰卞搷鏄庡ぉ鍏堥獙)')
        caffeine = st.checkbox('鏅氬挅鍟?(褰卞搷鏄庡ぉ鍏堥獙)')
        screen = st.checkbox('鐫″墠鐪嬪睆 (褰卞搷鏄庡ぉ鍏堥獙)')
        late_meal = st.checkbox('鏅氶澶櫄 (褰卞搷鏄庡ぉ鍏堥獙)')
    with c15:
        is_sick = st.checkbox('浠婂ぉ鐢熺梾 (褰卞搷浠婂ぉ鍚庨獙)')
        is_injured = st.checkbox('浠婂ぉ鍙椾激 (褰卞搷浠婂ぉ鍚庨獙)')
        high_stress_today = st.checkbox('浠婂ぉ楂樺帇浜嬩欢 (褰卞搷浠婂ぉ鍚庨獙)')
        meditation_done = st.checkbox('浠婂ぉ鍐ユ兂 (褰卞搷浠婂ぉ鍚庨獙)')

    # Build input dict for today
    today_inputs: Dict[str, Any] = {
        'date': st.session_state.date,
        'user_id': st.session_state.user_id,
        'gender': st.session_state.gender,
        'training_load': training_load,
        'apple_sleep_score': int(apple_sleep_score) if apple_sleep_score else None,
        'sleep_performance_state': None if sleep_perf == '(涓嶅～)' else sleep_perf,
        'restorative_sleep': None if restorative_sleep == '(涓嶅～)' else restorative_sleep,
        'hrv_trend': None if hrv_trend == '(涓嶅～)' else hrv_trend,
        'fatigue_hooper': int(fatigue_hooper) if fatigue_hooper else None,
        'soreness_hooper': int(soreness_hooper) if soreness_hooper else None,
        'stress_hooper': int(stress_hooper) if stress_hooper else None,
        'sleep_hooper': int(sleep_hooper) if sleep_hooper else None,
        'nutrition': None if nutrition == '(涓嶅～)' else nutrition,
        'gi_symptoms': None if gi_symptoms == '(涓嶅～)' else gi_symptoms,
        'is_sick': is_sick,
        'is_injured': is_injured,
        'high_stress_event_today': high_stress_today,
        'meditation_done_today': meditation_done,
        'cycle_day': int(cycle_day) if cycle_day else None,
        'cycle_length': int(cycle_length) if cycle_length else None,
    }

    # Compute today
    if st.button('璁＄畻浠婂ぉ鍑嗗搴?):
        payload = build_payload(today_inputs)
        res = compute_readiness_from_payload(payload)
        st.session_state.last_result = res

    # Show result
    if st.session_state.last_result:
        res = st.session_state.last_result
        st.success(f"浠婃棩鍑嗗搴? {res['final_readiness_score']} | 璇婃柇: {res['final_diagnosis']}")
        st.write('浣跨敤鐨勮瘉鎹?', list(res.get('evidence_pool', {}).keys()))
        # Posterior chart
        posterior = res.get('final_posterior_probs') or {}
        if posterior:
            chart_df = pd.DataFrame({'state': STATES, 'prob': [posterior.get(s, 0.0) for s in STATES]})
            st.bar_chart(chart_df, x='state', y='prob', height=240)

    st.markdown('---')
    c16, c17, c18 = st.columns(3)
    with c16:
        if st.button('淇濆瓨浠婂ぉ鍒癈SV'):
            row = {
                'date': st.session_state.date.strftime('%Y-%m-%d'),
                'user_id': st.session_state.user_id,
                'gender': st.session_state.gender,
                'training_load': training_load,
                'apple_sleep_score': today_inputs.get('apple_sleep_score'),
                'sleep_performance_state': today_inputs.get('sleep_performance_state'),
                'restorative_sleep': today_inputs.get('restorative_sleep'),
                'hrv_trend': today_inputs.get('hrv_trend'),
                'fatigue_hooper': today_inputs.get('fatigue_hooper'),
                'soreness_hooper': today_inputs.get('soreness_hooper'),
                'stress_hooper': today_inputs.get('stress_hooper'),
                'sleep_hooper': today_inputs.get('sleep_hooper'),
                'nutrition': today_inputs.get('nutrition'),
                'gi_symptoms': today_inputs.get('gi_symptoms'),
                # Journal
                'alcohol_consumed': bool(alcohol),
                'late_caffeine': bool(caffeine),
                'screen_before_bed': bool(screen),
                'late_meal': bool(late_meal),
                'is_sick': bool(is_sick),
                'is_injured': bool(is_injured),
                # Training extras
                'rpe': int(rpe),
                'duration_minutes': int(duration_min),
                'rpe_au': int(rpe_au),
                'label_au': int(label_au),
                'training_conflict': int(conflict),
            }
            # Result extras
            if st.session_state.last_result:
                row['final_readiness_score'] = int(st.session_state.last_result.get('final_readiness_score', 0))
                row['final_diagnosis'] = st.session_state.last_result.get('final_diagnosis')
            append_csv(row)
            st.success(f'宸插啓鍏SV: {st.session_state.csv_path}')

    with c17:
        if st.button('鍔犺浇CSV缁х画'):
            path = st.session_state.csv_path
            if os.path.exists(path):
                df = pd.read_csv(path)
                st.dataframe(df.tail(10))
            else:
                st.warning('CSV涓嶅瓨鍦?)

    with c18:
        if st.button('涓嬩竴澶?):
            # Prepare next day context
            # 1) Chain posterior -> previous_state_probs
            if st.session_state.last_result and st.session_state.last_result.get('final_posterior_probs'):
                st.session_state.prev_probs = st.session_state.last_result['final_posterior_probs']
            # 2) Short-term today -> pending for tomorrow
            st.session_state.short_term_pending = {
                'alcohol_consumed': bool(alcohol),
                'late_caffeine': bool(caffeine),
                'screen_before_bed': bool(screen),
                'late_meal': bool(late_meal),
            }
            # 3) Training for tomorrow: label wins; update AU list
            st.session_state.nextday_training_label = training_load
            if rpe_au > 0:
                arr = (st.session_state.recent_training_au + [float(rpe_au)])[-7:]
                st.session_state.recent_training_au = arr
            # 4) Advance date
            st.session_state.date = st.session_state.date + timedelta(days=1)
            st.info('宸叉帹杩涘埌涓嬩竴澶?)

    st.markdown('---')
    st.caption('璇存槑锛氱偣鍑烩€滆绠椾粖澶╁噯澶囧害鈥濋噸绠楀悗楠岋紱淇濆瓨鍚庣偣鈥滀笅涓€澶┾€濓紝绯荤粺鎶婁粖鏃ョ煭鏈熻涓哄拰璁粌鐢ㄤ簬鏄庡ぉ鍏堥獙锛宲osterior鑷姩閾惧紡鍒颁笅涓€澶┿€?)


if __name__ == '__main__':
    main()
