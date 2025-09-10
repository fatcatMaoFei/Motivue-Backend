#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绠€鍖栫殑涓€у寲EM瀛︿範绯荤粺

鍩轰簬鐜版湁鐨剆ervice.py鍜宑onstants.py锛屼娇鐢ㄧ畝鍖栫殑EM绠楁硶瀛︿範涓€у寲CPT琛?
杈撳叆锛?0澶╀互涓婄殑鐢ㄦ埛鍘嗗彶鏁版嵁CSV
杈撳嚭锛氫釜鎬у寲鐨凟MISSION_CPT JSON
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from . import constants
from . import service
from . import mapping


# -------------------- CSV normalization helpers --------------------
_NA_STRINGS = {"", "none", "null", "na", "nan", "None", "NULL", "NA", "NaN"}

def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize columns and coerce NA-like strings to real NaNs.

    - Ensures expected columns exist (missing -> NaN/None)
    - Coerces common NA strings ("", "none", "null", etc.) to NaN so pd.notna works
    - Parses date column to datetime and sorts
    """
    df = df.copy()
    # Coerce NA-like strings to NaN for object columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda v: None if (isinstance(v, str) and v.strip() in _NA_STRINGS) else v)

    # Ensure required columns exist
    required_cols = [
        'date', 'training_load', 'gender',
        'apple_sleep_score',
        'sleep_duration_hours', 'sleep_efficiency',
        'fatigue_hooper', 'soreness_hooper', 'stress_hooper', 'sleep_hooper',
        'hrv_trend', 'restorative_ratio',
        'nutrition', 'gi_symptoms',
        'alcohol_consumed', 'late_caffeine', 'screen_before_bed', 'late_meal',
        'is_sick', 'is_injured',
    ]
    for c in required_cols:
        if c not in df.columns:
            df[c] = None

    # Normalize date
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.sort_values('date')
    else:
        df = df.reset_index(drop=True)

    return df

def generate_sample_history_csv(user_id: str, days: int = 45, out_path: str = None) -> str:
    """鐢熸垚鏍锋湰鍘嗗彶鏁版嵁CSV鏂囦欢锛岀敤浜庝釜鎬у寲瀛︿範"""
    
    if out_path is None:
        out_path = f"user_history_{user_id}_{days}d.csv"
    
    # 鐢熸垚45澶╃殑鍘嗗彶鏁版嵁
    start_date = datetime(2025, 7, 1)  # 浠?鏈?鏃ュ紑濮?
    data = []
    
    random.seed(42)  # 鍥哄畾闅忔満绉嶅瓙浠ヤ究澶嶇幇
    
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # 妯℃嫙鐢ㄦ埛鏁版嵁妯″紡
        # Apple鐫＄湢璇勫垎 (iOS 26) - 浼樺厛浣跨敤
        apple_score = None
        sleep_duration = None
        sleep_efficiency = None
        
        # 70%姒傜巼鏈堿pple璇勫垎锛?0%浣跨敤浼犵粺鏁版嵁
        if random.random() < 0.7:
            # 妯℃嫙Apple璇勫垎瓒嬪娍锛氬懆鏈◢濂斤紝宸ヤ綔鏃ユ尝鍔?
            is_weekend = current_date.weekday() >= 5
            base_score = 78 if is_weekend else 73
            apple_score = max(40, min(100, base_score + random.randint(-15, +20)))
            # 鏈堿pple璇勫垎鏃讹紝浼犵粺鐫＄湢鏁版嵁璁句负null
            sleep_duration = None
            sleep_efficiency = None
        else:
            # 浼犵粺鐫＄湢鏁版嵁
            sleep_duration = round(random.uniform(6.5, 8.5), 1)
            sleep_efficiency = round(random.uniform(0.75, 0.92), 3)
            # 鏈変紶缁熸暟鎹椂锛孉pple璇勫垎璁句负null
            apple_score = None
        
        # Hooper閲忚〃 (1-7)
        fatigue_hooper = random.randint(1, 5)
        soreness_hooper = random.randint(1, 4) 
        stress_hooper = random.randint(1, 4)
        sleep_hooper = random.randint(2, 5)
        
        # HRV瓒嬪娍
        hrv_trend = random.choice(['rising', 'stable', 'stable', 'slight_decline'])
        
        # 璁粌璐熻嵎
        training_load = random.choice(['低','中','高','极高','休息'])  # 鍋忓悜涓綆寮哄害
        
        # 鎭㈠鎬х潯鐪?
        restorative_ratio = round(random.uniform(0.65, 0.88), 3)
        
        # 钀ュ吇鍜屽叾浠?
        nutrition = random.choice(['adequate', 'adequate', 'inadequate_mild'])
        gi_symptoms = random.choice(['none', 'none', 'none', 'mild'])
        
        # 鏃ュ織鏁版嵁 (鏄ㄥぉ琛屼负褰卞搷浠婂ぉ)
        alcohol_consumed = random.random() < 0.15  # 15%姒傜巼
        late_caffeine = random.random() < 0.20     # 20%姒傜巼
        screen_before_bed = random.random() < 0.35 # 35%姒傜巼
        late_meal = random.random() < 0.12         # 12%姒傜巼
        
        # 鐤剧梾/鍙椾激 (鎸佺画鐘舵€?
        is_sick = random.random() < 0.05     # 5%姒傜巼
        is_injured = random.random() < 0.03  # 3%姒傜巼
        
        row = {
            # 鍩烘湰淇℃伅锛堝繀濉級
            'date': date_str,
            'user_id': user_id,
            'gender': '男性',  # 固定
            'training_load': training_load,
            
            # 鐫＄湢鏁版嵁锛堜簩閫変竴锛宯ull鏃朵负None锛?
            'apple_sleep_score': apple_score,  # null or int
            'sleep_duration_hours': sleep_duration,  # null or float
            'sleep_efficiency': sleep_efficiency,  # null or float
            
            # Hooper閲忚〃锛?-7锛宯ull鏃朵负None锛?
            'fatigue_hooper': fatigue_hooper,
            'soreness_hooper': soreness_hooper,
            'stress_hooper': stress_hooper,
            'sleep_hooper': sleep_hooper,
            
            # 鍏朵粬瀹㈣鎸囨爣锛坣ull鏃朵负None锛?
            'hrv_trend': hrv_trend,
            'restorative_ratio': restorative_ratio,
            
            # 钀ュ吇鍜岀棁鐘讹紙null鏃朵负None锛?
            'nutrition': nutrition,
            'gi_symptoms': gi_symptoms,
            
            # 鏄ㄥぉ琛屼负鏃ュ織锛坆ool锛宯ull鏃朵负False锛?
            'alcohol_consumed': alcohol_consumed,
            'late_caffeine': late_caffeine,
            'screen_before_bed': screen_before_bed,
            'late_meal': late_meal,
            
            # 浠婂ぉ鎸佺画鐘舵€侊紙bool锛宯ull鏃朵负False锛?
            'is_sick': is_sick,
            'is_injured': is_injured,
        }
        
        data.append(row)
    
    # 淇濆瓨CSV
    df = pd.DataFrame(data)
    df.to_csv(out_path, index=False, encoding='utf-8')
    
    print(f"鐢熸垚鏍锋湰鍘嗗彶鏁版嵁: {out_path}")
    print(f"  澶╂暟: {days}")
    print(f"  Apple璇勫垎鏁版嵁: {sum(1 for r in data if r['apple_sleep_score'] is not None)} 澶?)
    print(f"  浼犵粺鐫＄湢鏁版嵁: {sum(1 for r in data if r['sleep_duration_hours'] is not None)} 澶?)
    
    return out_path


def csv_row_to_payload(row: pd.Series, user_id: str) -> Dict[str, Any]:
    """灏咰SV琛岃浆鎹负readiness payload鏍煎紡
    鏀寔鍥哄畾鏍煎紡鐨凜SV锛屾墍鏈夊垪閮藉瓨鍦紝null鍊肩敤None/NaN琛ㄧず
    """
    
    payload = {
        'user_id': user_id,
        'date': (row['date'].strftime('%Y-%m-%d') if hasattr(row['date'],'strftime') else row['date']),
        'gender': str(row.get('gender', '鐢?)),  # 浠嶤SV璇诲彇鎬у埆锛岄粯璁ょ敺
    }
    
    # 鎬у埆榛樿鍊间慨姝?    try:
        g = payload.get('gender')
        if g is None or str(g).strip().lower() in ['','none','null','nan']:
            payload['gender'] = '鐢锋€?
    except Exception:
        payload['gender'] = '鐢锋€?

    # 璁粌璐熻嵎锛堢敤浜庡厛楠岋級
    try:
        if pd.notna(row.get('training_load')):
            payload['training_load'] = str(row['training_load'])
    except Exception:
        pass

    # Apple鐫＄湢璇勫垎锛坣ull鏃惰烦杩囷級
    if pd.notna(row.get('apple_sleep_score')):
        try:
            payload['apple_sleep_score'] = int(float(row['apple_sleep_score']))
        except (ValueError, TypeError):
            pass
    
    # 浼犵粺鐫＄湢鏁版嵁锛坣ull鏃惰烦杩囷級
    if pd.notna(row.get('sleep_duration_hours')):
        try:
            payload['sleep_duration_hours'] = float(row['sleep_duration_hours'])
        except (ValueError, TypeError):
            pass
    
    if pd.notna(row.get('sleep_efficiency')):
        try:
            payload['sleep_efficiency'] = float(row['sleep_efficiency'])
        except (ValueError, TypeError):
            pass
    
    # Hooper閲忚〃锛堟瀯寤哄畬鏁寸殑hooper瀛楀吀锛宯ull鍊艰烦杩囧搴旈」锛?
    hooper = {}
    for h in ['fatigue', 'soreness', 'stress', 'sleep']:
        key = f'{h}_hooper'
        if pd.notna(row.get(key)):
            try:
                hooper[h] = int(float(row[key]))
            except (ValueError, TypeError):
                pass
    
    if hooper:  # 鑷冲皯鏈変竴椤筯ooper鏁版嵁鎵嶆坊鍔?
        payload['hooper'] = hooper
    
    # 鍏朵粬瀹㈣鏁版嵁锛坣ull鏃惰烦杩囷級
    if pd.notna(row.get('hrv_trend')):
        payload['hrv_trend'] = str(row['hrv_trend']).strip()
    
    if pd.notna(row.get('restorative_ratio')):
        try:
            payload['restorative_ratio'] = float(row['restorative_ratio'])
        except (ValueError, TypeError):
            pass
    
    if pd.notna(row.get('nutrition')):
        payload['nutrition'] = str(row['nutrition']).strip()
    
    if pd.notna(row.get('gi_symptoms')):
        payload['gi_symptoms'] = str(row['gi_symptoms']).strip()
    
    # 鏃ュ織鏁版嵁锛堟瀯寤哄畬鏁寸殑journal瀛楀吀锛宯ull鍊奸粯璁alse锛?
    journal = {}
    journal_keys = ['alcohol_consumed', 'late_caffeine', 'screen_before_bed', 'late_meal', 'is_sick', 'is_injured']
    
    for key in journal_keys:
        if pd.notna(row.get(key)):
            value = row[key]
            if isinstance(value, str):
                # 鏀寔 "true"/"false", "1"/"0", "yes"/"no" 绛夋牸寮?
                journal[key] = value.strip().lower() in ['true', '1', 'yes', 'y']
            else:
                journal[key] = bool(value)
        else:
            # null鍊奸粯璁alse
            journal[key] = False
    
    payload['journal'] = journal
    
    return payload


def learn_personalized_cpt(df: pd.DataFrame, user_id: str, shrinkage_k: float = 100.0) -> Dict[str, Any]:
    """浠庡巻鍙叉暟鎹涔犱釜鎬у寲CPT琛?""
    
    print(f"\n寮€濮嬩负鐢ㄦ埛 {user_id} 瀛︿範涓€у寲CPT琛?..")
    print(f"鍘嗗彶鏁版嵁: {len(df)} 澶?)
    
    # 妫€鏌ユ暟鎹噺鏄惁瓒冲锛堚墺30澶╋級
    if len(df) < 30:
        print(f"鏁版嵁涓嶈冻30澶╋紝浣跨敤榛樿CPT琛?)
        return deepcopy(constants.EMISSION_CPT)
    
    # 缁熻璇佹嵁璁℃暟
    evidence_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))  # evidence_type -> level -> state -> count
    state_totals = defaultdict(lambda: defaultdict(float))  # evidence_type -> state -> count
    
    prev_probs = None
    
    for idx, row in df.iterrows():
        # 杞崲涓簆ayload鏍煎紡
        payload = csv_row_to_payload(row, user_id)
        # 纭繚鏃ユ湡鏄瓧绗︿覆鏍煎紡
        if hasattr(row['date'], 'strftime'):
            payload['date'] = row['date'].strftime('%Y-%m-%d')
        payload['previous_state_probs'] = prev_probs
        
        # 鑾峰彇readiness璁＄畻缁撴灉
        try:
            # Normalize gender just before calling the service
            g = str(payload.get('gender') or '').strip()
            if g not in ('鐢锋€?, '濂虫€?):
                payload['gender'] = '鐢锋€?

            result = service.compute_readiness_from_payload(payload)
            posterior_probs = result.get('final_posterior_probs', result.get('posterior_probs', {}))
            
            # 鏄犲皠杈撳叆鍒拌瘉鎹姸鎬?
            mapped_evidence = mapping.map_inputs_to_states(payload)
            
            # 绱Н璁℃暟 (E-step)
            for evidence_type, level in mapped_evidence.items():
                if evidence_type in constants.EMISSION_CPT:
                    # 瀵规瘡涓姸鎬佹寜鍚庨獙姒傜巼鍔犳潈璁℃暟
                    for state in ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']:
                        weight = posterior_probs.get(state, 0.0)
                        evidence_counts[evidence_type][level][state] += weight
                        state_totals[evidence_type][state] += weight
            
            # 鏇存柊鍓嶄竴澶╂鐜?
            prev_probs = posterior_probs
            
        except Exception as e:
            print(f"  璺宠繃绗瑊idx+1}澶╂暟鎹? {e}")
            continue
    
    # M-step: 閲嶄及璁℃鐜?
    print(f"寮€濮婱-step閲嶄及璁?..")
    
    learned_cpt = deepcopy(constants.EMISSION_CPT)
    
    for evidence_type in evidence_counts:
        if evidence_type not in constants.EMISSION_CPT:
            continue
        
        # 妫€鏌ヨ繖涓瘉鎹被鍨嬫槸鍚︽湁瓒冲鏁版嵁锛堣嚦灏?0涓牱鏈級
        total_samples = sum(state_totals[evidence_type].values())
        if total_samples < 10:
            print(f"  {evidence_type}: 鏁版嵁涓嶈冻({total_samples:.1f}鏍锋湰)锛屼繚鎸侀粯璁PT")
            continue
            
        print(f"  澶勭悊璇佹嵁绫诲瀷: {evidence_type} ({total_samples:.1f}鏍锋湰)")
        
        for level in constants.EMISSION_CPT[evidence_type]:
            for state in ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']:
                # 鍘熷鍏ㄥ眬姒傜巼
                global_prob = constants.EMISSION_CPT[evidence_type][level][state]
                
                # 瀛︿範鍒扮殑姒傜巼
                count = evidence_counts[evidence_type][level][state]
                state_total = state_totals[evidence_type][state]
                
                if state_total > 0:
                    learned_prob = count / state_total
                else:
                    learned_prob = global_prob
                
                # 搴旂敤鏀剁缉 (shrinkage)
                # 伪 = n / (n + k), 娣峰悎姒傜巼 = 伪 * learned + (1-伪) * global
                alpha = state_total / (state_total + shrinkage_k)
                mixed_prob = alpha * learned_prob + (1 - alpha) * global_prob
                
                learned_cpt[evidence_type][level][state] = max(1e-6, mixed_prob)
    
    return learned_cpt


def save_personalized_cpt(cpt: Dict[str, Any], user_id: str, out_path: str = None) -> str:
    """淇濆瓨涓€у寲CPT鍒癑SON鏂囦欢"""
    
    if out_path is None:
        out_path = f"personalized_emission_cpt_{user_id}.json"
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(cpt, f, ensure_ascii=False, indent=2)
    
    print(f"淇濆瓨涓€у寲CPT: {out_path}")
    return out_path


def load_personalized_cpt(in_path: str) -> None:
    """Load a personalized EMISSION_CPT JSON into running constants."""
    with open(in_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    constants.EMISSION_CPT = loaded
    print(f"Loaded personalized EMISSION_CPT from: {in_path}")


def preview_cpt_changes(original_cpt: Dict[str, Any], personalized_cpt: Dict[str, Any], top_changes: int = 5):
    """棰勮CPT鍙樺寲"""
    
    print(f"\n=== CPT涓€у寲鍙樺寲棰勮 (Top {top_changes}) ===")
    
    all_changes = []
    
    for evidence_type in personalized_cpt:
        if evidence_type not in original_cpt:
            continue
            
        for level in personalized_cpt[evidence_type]:
            if level not in original_cpt[evidence_type]:
                continue
                
            for state in ['Peak', 'Well-adapted', 'NFOR', 'OTS']:
                orig_prob = original_cpt[evidence_type][level][state]
                pers_prob = personalized_cpt[evidence_type][level][state]
                change = pers_prob - orig_prob
                
                if abs(change) > 0.001:  # 鍙樉绀烘樉钁楀彉鍖?
                    all_changes.append({
                        'evidence': evidence_type,
                        'level': level,
                        'state': state,
                        'original': orig_prob,
                        'personalized': pers_prob,
                        'change': change,
                        'change_abs': abs(change)
                    })
    
    # 鎸夊彉鍖栧箙搴︽帓搴?
    all_changes.sort(key=lambda x: x['change_abs'], reverse=True)
    
    for i, c in enumerate(all_changes[:top_changes]):
        print(f"{i+1:2d}. {c['evidence']:>18} | {c['level']:>12} | {c['state']:>12} | "
              f"{c['original']:6.3f} 鈫?{c['personalized']:6.3f} | "
              f"螖 {c['change']:+.3f}")


def main():
    """涓诲嚱鏁?""
    
    ap = argparse.ArgumentParser(description="绠€鍖栫殑涓€у寲CPT瀛︿範绯荤粺")
    ap.add_argument('--user', required=True, help='鐢ㄦ埛ID')
    ap.add_argument('--csv', help='鍘嗗彶鏁版嵁CSV鏂囦欢璺緞')
    ap.add_argument('--days', type=int, default=45, help='濡傛灉娌℃湁CSV锛岀敓鎴愭牱鏈暟鎹殑澶╂暟')
    ap.add_argument('--shrink-k', type=float, default=100.0, help='鏀剁缉鍙傛暟K')
    ap.add_argument('--out', help='杈撳嚭JSON鏂囦欢璺緞')
    args = ap.parse_args()
    
    # 濡傛灉娌℃湁鎻愪緵CSV锛岀敓鎴愭牱鏈暟鎹?
    if not args.csv:
        print(f"娌℃湁鎻愪緵CSV鏂囦欢锛岀敓鎴恵args.days}澶╂牱鏈暟鎹?..")
        csv_path = generate_sample_history_csv(args.user, args.days)
    else:
        csv_path = args.csv
    
    # 璇诲彇鍘嗗彶鏁版嵁
    print(f"\n璇诲彇鍘嗗彶鏁版嵁: {csv_path}")
    # Robust CSV parsing: coerce common NA-like strings to NaN and standardize
    na_vals = ["", "none", "null", "na", "nan", "None", "NULL", "NA", "NaN"]
    df = pd.read_csv(csv_path, na_values=na_vals, keep_default_na=True)
    df = _normalize_history_df(df)
    
    print(f"鏁版嵁姒傝:")
    print(f"  鎬诲ぉ鏁? {len(df)}")
    print(f"  鏃ユ湡鑼冨洿: {df['date'].min().date()} 鍒?{df['date'].max().date()}")
    print(f"  Apple璇勫垎鏁版嵁: {df['apple_sleep_score'].notna().sum()} 澶?)
    print(f"  浼犵粺鐫＄湢鏁版嵁: {df['sleep_duration_hours'].notna().sum()} 澶?)
    
    # 瀛︿範涓€у寲CPT
    personalized_cpt = learn_personalized_cpt(df, args.user, args.shrink_k)
    
    # 淇濆瓨缁撴灉
    out_path = save_personalized_cpt(personalized_cpt, args.user, args.out)
    
    # 棰勮鍙樺寲
    preview_cpt_changes(constants.EMISSION_CPT, personalized_cpt, top_changes=10)
    
    print(f"\n[瀹屾垚] 涓€у寲瀛︿範瀹屾垚锛?)
    print(f"   杈撳嚭鏂囦欢: {out_path}")
    
    return out_path


if __name__ == '__main__':
    main()



