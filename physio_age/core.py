from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


_MALE_FILE = Path('physio_age/hrv_age_table.csv')
_FEMALE_FILE = Path('physio_age/hrv_age_table_female.csv')


def _norm_gender(g: Any) -> str:
    s = (str(g) if g is not None else '').strip().lower()
    if s in {'男', '男性', 'male', 'm'}:
        return 'male'
    if s in {'女', '女性', 'female', 'f'}:
        return 'female'
    # default to male if unspecified
    return 'male'


def _load_master_table(gender: str) -> Dict[int, Dict[str, float]]:
    path = _MALE_FILE if gender == 'male' else _FEMALE_FILE
    if not path.exists():
        raise FileNotFoundError(f'Master table not found: {path}')

    # Accept Chinese header '年龄' or 'age'
    # Columns required: SDNN_mu, SDNN_sigma, RHR_mu, RHR_sigma, CSS_mu, CSS_sigma
    out: Dict[int, Dict[str, float]] = {}
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # normalize headers: strip spaces
        field_map = {k.strip(): k for k in reader.fieldnames or []}
        age_key = '年龄' if '年龄' in field_map else ('age' if 'age' in field_map else None)
        req = ['SDNN_mu', 'SDNN_sigma', 'RHR_mu', 'RHR_sigma', 'CSS_mu', 'CSS_sigma']
        if age_key is None or not all(k in field_map for k in req):
            raise ValueError('Master table missing required columns: 年龄/age and SDNN_mu/SDNN_sigma/RHR_mu/RHR_sigma/CSS_mu/CSS_sigma')
        for row in reader:
            try:
                age = int(float(row[field_map[age_key]].strip()))
            except Exception:
                continue
            try:
                entry = {
                    'SDNN_mu': float(row[field_map['SDNN_mu']]),
                    'SDNN_sigma': float(row[field_map['SDNN_sigma']]),
                    'RHR_mu': float(row[field_map['RHR_mu']]),
                    'RHR_sigma': float(row[field_map['RHR_sigma']]),
                    'CSS_mu': float(row[field_map['CSS_mu']]),
                    'CSS_sigma': float(row[field_map['CSS_sigma']]),
                }
                out[age] = entry
            except Exception:
                # skip malformed rows
                continue
    return out


def _z(x: float, mu: float, sigma: float) -> Optional[float]:
    if sigma is None or sigma <= 1e-6:
        return None
    return (x - mu) / sigma


def _cost_for_age(sdnn: float, rhr: float, css: float, norms: Dict[str, float],
                  w_sdnn: float, w_rhr: float, w_css: float) -> Optional[Tuple[float, Dict[str, float]]]:
    z_sdnn = _z(sdnn, norms['SDNN_mu'], norms['SDNN_sigma'])
    z_rhr = _z(rhr, norms['RHR_mu'], norms['RHR_sigma'])
    z_css = _z(css, norms['CSS_mu'], norms['CSS_sigma'])
    if z_sdnn is None or z_rhr is None or z_css is None:
        return None
    # Reverse RHR so that higher is worse → multiply by -1 to align positive as better
    z_rhr = -z_rhr
    # Weighted squared z
    c = w_sdnn * (z_sdnn ** 2) + w_rhr * (z_rhr ** 2) + w_css * (z_css ** 2)
    return c, {'z_sdnn': z_sdnn, 'z_rhr': z_rhr, 'z_css': z_css}


def _weighted_age(costs: List[Tuple[int, float]], tau: float = 0.2) -> float:
    if not costs:
        return float('nan')
    # Softmin weights around the minimum cost
    min_c = min(c for _, c in costs)
    ws = [math.exp(-(c - min_c) / max(tau, 1e-6)) for _, c in costs]
    denom = sum(ws) or 1.0
    num = sum(age * w for (age, c), w in zip(costs, ws))
    return num / denom


def compute_physiological_age(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compute physiological age by minimizing weighted z-score mismatch vs norms.

    Required payload keys:
      - daily_SDNN (ms), daily_RHR (bpm), daily_CSS (0..100), user_gender ('男性'/'女性' or 'male'/'female')

    Optional:
      - age_min (int, default 20), age_max (int, default 80)
      - weights: {'sdnn': 0.45, 'rhr': 0.20, 'css': 0.35}
      - softmin_tau (float, default 0.2) for fractional weighted age
    """
    # Determine inputs from series (preferred) or daily values
    sdnn_series = payload.get('sdnn_series')
    rhr_series = payload.get('rhr_series')

    if isinstance(sdnn_series, list) and isinstance(rhr_series, list):
        try:
            sdnn_series_f = [float(x) for x in sdnn_series if x is not None]
            rhr_series_f = [float(x) for x in rhr_series if x is not None]
        except Exception:
            return {'status': 'error', 'message': 'sdnn_series/rhr_series must be numeric lists'}
        if len(sdnn_series_f) < 30 or len(rhr_series_f) < 30:
            return {'status': 'error', 'message': 'At least 30 days of sdnn_series and rhr_series are required'}
        # Use last 30 days mean as baseline inputs
        sdnn_val = mean(sdnn_series_f[-30:])
        rhr_val = mean(rhr_series_f[-30:])
        window_days_used = 30
        data_days_count = min(len(sdnn_series_f), len(rhr_series_f))
    else:
        # Fallback to daily values (not recommended if 30d requirement enforced)
        try:
            sdnn_val = float(payload.get('daily_SDNN'))
            rhr_val = float(payload.get('daily_RHR'))
        except Exception:
            return {'status': 'error', 'message': 'Provide sdnn_series/rhr_series (>=30d) or daily_SDNN/daily_RHR'}
        window_days_used = 1
        data_days_count = 1

    # CSS from today sleep signals (absolute, no baseline)
    css_val = payload.get('daily_CSS')
    if css_val is None:
        try:
            from physio_age.css import compute_css
            css_res = compute_css(payload)
            css_val = css_res.get('daily_CSS')
        except Exception:
            css_val = None
    try:
        css = float(css_val)
    except Exception:
        return {'status': 'error', 'message': 'Unable to compute daily_CSS from provided sleep inputs'}

    gender = _norm_gender(payload.get('user_gender'))
    table = _load_master_table(gender)

    age_min = int(payload.get('age_min') or 20)
    age_max = int(payload.get('age_max') or 80)
    if age_min > age_max:
        age_min, age_max = age_max, age_min

    w = payload.get('weights') or {}
    w_sdnn = float(w.get('sdnn', 0.45))
    w_rhr = float(w.get('rhr', 0.20))
    w_css = float(w.get('css', 0.35))

    candidates = []  # (age, cost, z_dict)
    for age in range(age_min, age_max + 1):
        norms = table.get(age)
        if not norms:
            continue
        res = _cost_for_age(sdnn_val, rhr_val, css, norms, w_sdnn, w_rhr, w_css)
        if res is None:
            continue
        cost, zdict = res
        candidates.append((age, cost, zdict))

    if not candidates:
        return {'status': 'error', 'message': 'No valid candidates; check norms table and inputs'}

    # Select minimal cost
    best_age, best_cost, best_z = min(candidates, key=lambda x: x[1])

    # Fractional weighted age using softmin around min cost
    tau = float(payload.get('softmin_tau') or 0.2)
    costs_for_weight = [(age, cost) for age, cost, _ in candidates]
    weighted_age = _weighted_age(costs_for_weight, tau=tau)

    return {
        'status': 'ok',
        'physiological_age': int(best_age),
        'physiological_age_weighted': round(float(weighted_age), 1),
        'best_cost': float(best_cost),
        'best_age_zscores': best_z,
        'window_days_used': window_days_used,
        'data_days_count': data_days_count,
    }
