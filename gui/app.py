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
    return best_label or '休息'


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
    if today_inputs.get('gender') == '女性':
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
    st.set_page_config(page_title='Readiness 手工录入与测试', layout='wide')
    init_state()

    st.sidebar.header('全局设置')
    st.session_state.csv_path = st.sidebar.text_input('CSV保存路径', st.session_state.csv_path)

    colA, colB, colC = st.columns(3)
    with colA:
        st.session_state.user_id = st.text_input('用户ID', st.session_state.user_id)
        st.session_state.gender = st.selectbox('性别', ['男性', '女性'], index=0 if st.session_state.gender=='男性' else 1)
    with colB:
        st.session_state.date = st.date_input('日期', st.session_state.date)
    with colC:
        st.write('上一日状态分布 (首日可重置)')
        if st.button('重置初始分布', help='重置为 [0.2,0.4,0.3,0.1,0,0]'):
            st.session_state.prev_probs = {
                'Peak': 0.2, 'Well-adapted': 0.4, 'FOR': 0.3,
                'Acute Fatigue': 0.1, 'NFOR': 0.0, 'OTS': 0.0
            }
        st.json(st.session_state.prev_probs)

    st.markdown('---')
    st.subheader('训练强度（用于明天先验；标签为准，记录RPE×分钟AU）')
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        training_load = st.selectbox('今日强度标签', ['极高','高','中','低','休息'])
    with c2:
        rpe = st.number_input('RPE(1..10)', min_value=0, max_value=10, value=0, step=1)
    with c3:
        duration_min = st.number_input('训练时长(分钟)', min_value=0, max_value=1000, value=0, step=10)
    with c4:
        st.write('说明：标签用于今日先验；RPE×分钟用于明天AU序列。')

    rpe_au = int(rpe * duration_min) if (rpe and duration_min) else 0
    label_au = int(label_to_au(training_load))
    inferred_label_from_rpe = au_to_label_by_nearest(rpe_au) if rpe_au>0 else None
    conflict = 1 if (inferred_label_from_rpe and inferred_label_from_rpe != training_load) else 0
    st.caption(f'RPE×分钟 AU={rpe_au}；标签AU={label_au}；RPE→标签={inferred_label_from_rpe or "N/A"}；冲突={bool(conflict)}')

    st.markdown('---')
    st.subheader('睡眠与HRV（今天后验）')
    c5, c6, c7 = st.columns(3)
    with c5:
        apple_sleep_score = st.number_input('苹果睡眠分(0-100)', min_value=0, max_value=100, value=0, step=1)
        sleep_perf = st.selectbox('传统睡眠表现', ['(不填)','good','medium','poor'], index=0)
    with c6:
        restorative_sleep = st.selectbox('恢复性睡眠', ['(不填)','high','medium','low'], index=0)
        hrv_trend = st.selectbox('HRV趋势', ['(不填)','rising','stable','slight_decline','significant_decline'], index=0)
    with c7:
        gender = st.session_state.gender
        cycle_day = st.number_input('周期日(day)', min_value=0, max_value=60, value=0, step=1)
        cycle_length = st.number_input('周期长度(length)', min_value=0, max_value=60, value=0, step=1)

    st.markdown('---')
    st.subheader('Hooper（1..7）与其它（今天后验）')
    c8, c9, c10, c11 = st.columns(4)
    with c8:
        fatigue_hooper = st.number_input('疲劳 Hooper', min_value=0, max_value=7, value=0, step=1)
    with c9:
        soreness_hooper = st.number_input('酸痛 Hooper', min_value=0, max_value=7, value=0, step=1)
    with c10:
        stress_hooper = st.number_input('压力 Hooper', min_value=0, max_value=7, value=0, step=1)
    with c11:
        sleep_hooper = st.number_input('睡眠 Hooper', min_value=0, max_value=7, value=0, step=1)

    c12, c13 = st.columns(2)
    with c12:
        nutrition = st.selectbox('营养', ['(不填)','adequate','inadequate_mild','inadequate_moderate','inadequate_severe'], index=0)
    with c13:
        gi_symptoms = st.selectbox('GI症状', ['(不填)','none','mild','severe'], index=0)

    st.markdown('---')
    st.subheader('Journal 勾选（短期→明天先验；当日→今天后验）')
    c14, c15 = st.columns(2)
    with c14:
        alcohol = st.checkbox('昨晚饮酒 (影响明天先验)')
        caffeine = st.checkbox('晚咖啡 (影响明天先验)')
        screen = st.checkbox('睡前看屏 (影响明天先验)')
        late_meal = st.checkbox('晚餐太晚 (影响明天先验)')
    with c15:
        is_sick = st.checkbox('今天生病 (影响今天后验)')
        is_injured = st.checkbox('今天受伤 (影响今天后验)')
        high_stress_today = st.checkbox('今天高压事件 (影响今天后验)')
        meditation_done = st.checkbox('今天冥想 (影响今天后验)')

    # Build input dict for today
    today_inputs: Dict[str, Any] = {
        'date': st.session_state.date,
        'user_id': st.session_state.user_id,
        'gender': st.session_state.gender,
        'training_load': training_load,
        'apple_sleep_score': int(apple_sleep_score) if apple_sleep_score else None,
        'sleep_performance_state': None if sleep_perf == '(不填)' else sleep_perf,
        'restorative_sleep': None if restorative_sleep == '(不填)' else restorative_sleep,
        'hrv_trend': None if hrv_trend == '(不填)' else hrv_trend,
        'fatigue_hooper': int(fatigue_hooper) if fatigue_hooper else None,
        'soreness_hooper': int(soreness_hooper) if soreness_hooper else None,
        'stress_hooper': int(stress_hooper) if stress_hooper else None,
        'sleep_hooper': int(sleep_hooper) if sleep_hooper else None,
        'nutrition': None if nutrition == '(不填)' else nutrition,
        'gi_symptoms': None if gi_symptoms == '(不填)' else gi_symptoms,
        'is_sick': is_sick,
        'is_injured': is_injured,
        'high_stress_event_today': high_stress_today,
        'meditation_done_today': meditation_done,
        'cycle_day': int(cycle_day) if cycle_day else None,
        'cycle_length': int(cycle_length) if cycle_length else None,
    }

    # Compute today
    if st.button('计算今天准备度'):
        payload = build_payload(today_inputs)
        res = compute_readiness_from_payload(payload)
        st.session_state.last_result = res

    # Show result
    if st.session_state.last_result:
        res = st.session_state.last_result
        st.success(f"今日准备度: {res['final_readiness_score']} | 诊断: {res['final_diagnosis']}")
        st.write('使用的证据:', list(res.get('evidence_pool', {}).keys()))
        # Posterior chart
        posterior = res.get('final_posterior_probs') or {}
        if posterior:
            chart_df = pd.DataFrame({'state': STATES, 'prob': [posterior.get(s, 0.0) for s in STATES]})
            st.bar_chart(chart_df, x='state', y='prob', height=240)

    st.markdown('---')
    c16, c17, c18 = st.columns(3)
    with c16:
        if st.button('保存今天到CSV'):
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
            st.success(f'已写入CSV: {st.session_state.csv_path}')

    with c17:
        if st.button('加载CSV继续'):
            path = st.session_state.csv_path
            if os.path.exists(path):
                df = pd.read_csv(path)
                st.dataframe(df.tail(10))
            else:
                st.warning('CSV不存在')

    with c18:
        if st.button('下一天'):
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
            st.info('已推进到下一天')

    st.markdown('---')
    st.caption('说明：点击“计算今天准备度”重算后验；保存后点“下一天”，系统把今日短期行为和训练用于明天先验，posterior自动链式到下一天。')


if __name__ == '__main__':
    main()

