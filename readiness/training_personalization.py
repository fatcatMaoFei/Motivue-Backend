#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""Per-user training intensity personalization.

Goals
-----
- Log per-session training inputs (label + AU).
- Learn personalized AU thresholds for labels ['无','低','中','高','极高'].
- Provide mapping helpers label->AU and AU->label.
- Lay a hook for later bandit/RL-style fine tuning.

Design
------
- Storage: lightweight JSON file at readiness/_data/training_personalization.json
  (created lazily). Structure:
    { user_id: {
        'samples': [{date, au, label, weight}],
        'thresholds': {'b1':..., 'b2':..., 'b3':..., 'b4':..., 'version': int},
        'updated_at': 'YYYY-MM-DD',
      } }

- Default thresholds follow constants.TRaining_LOAD_AU midpoints; we fall back
  to them when sample size is insufficient.

- Personalization algorithm (v1):
  * Require at least MIN_TOTAL_SAMPLES and spread across at least 3 labels.
  * Compute per-label robust medians (5-95% clipped) and derive boundaries as
    midpoints between neighboring label medians. Interpolate with defaults when
    missing labels. Apply EMA smoothing with factor EMA_BETA.
  * Optionally, a simple bandit nudger (epsilon-greedy) adjusts boundaries by a
    small step when recent mismatch between (AU -> label) and user-provided
    labels is high. This is kept very conservative by limits and cooldown.

Note: RL/bandit hook is intentionally simple in v1; can be replaced by a
contextual bandit or Bayesian update later without changing the public API.
"""

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


LABELS = ['无', '低', '中', '高', '极高']


def _project_root() -> str:
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, os.pardir))


DATA_DIR = os.path.join(_project_root(), "readiness", "_data")
DATA_PATH = os.path.join(DATA_DIR, "training_personalization.json")


DEFAULT_THRESHOLDS = {
    # boundaries between labels (无|低|中|高|极高): [b1,b2,b3,b4]
    # Derived from AU midpoints of constants: 0,200,350,500,700
    'b1': 100.0,  # 无-低 midpoint
    'b2': 275.0,  # 低-中 midpoint
    'b3': 425.0,  # 中-高 midpoint
    'b4': 600.0,  # 高-极高 midpoint
    'version': 1,
}

MIN_TOTAL_SAMPLES = 30
EMA_BETA = 0.8  # smoothing factor for boundaries (higher=more conservative)
# Shrinkage schedule: alpha = min(1, n_valid / SHRINK_FULL_AT)
# So at n_valid=30 => alpha≈0.5 ; at n_valid=60 => alpha=1.0
SHRINK_FULL_AT = 60
BANDIT_EPS = 0.05
BANDIT_STEP = 10.0  # AU small step for nudging
BANDIT_WINDOW = 20
COOLDOWN_DAYS = 3


def _ensure_store() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def _load_db() -> Dict[str, Any]:
    _ensure_store()
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_db(db: Dict[str, Any]) -> None:
    _ensure_store()
    tmp = DATA_PATH + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_PATH)


def _today_str() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def _get_user(db: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    if user_id not in db:
        db[user_id] = {
            'samples': [],
            'thresholds': dict(DEFAULT_THRESHOLDS),
            'updated_at': None,
        }
    return db[user_id]


def add_training_sample(user_id: str, date: str, au: Optional[float], label: Optional[str], weight: float = 1.0) -> None:
    """Append a single session sample for a user.

    Args:
      user_id: user key
      date: 'YYYY-MM-DD'
      au: AU value (float) or None
      label: one of LABELS or None
      weight: sample weight (>=0); if both AU and label provided, you can pass >1.0
    """
    db = _load_db()
    u = _get_user(db, user_id)
    rec = {
        'date': date,
        'au': float(au) if au is not None else None,
        'label': label if label in LABELS else None,
        'weight': float(max(0.0, weight)),
    }
    u['samples'].append(rec)
    _save_db(db)


def _clipped(values: List[float], lo_q: float = 0.05, hi_q: float = 0.95) -> List[float]:
    if not values:
        return []
    xs = sorted(values)
    n = len(xs)
    lo_i = int(math.floor(n * lo_q))
    hi_i = int(math.ceil(n * hi_q))
    return xs[lo_i:hi_i] if lo_i < hi_i else xs


def _median(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    xs = sorted(xs)
    m = len(xs)
    mid = m // 2
    return float(xs[mid]) if m % 2 == 1 else float((xs[mid - 1] + xs[mid]) / 2.0)


def _midpoint(a: Optional[float], b: Optional[float], default: float) -> float:
    if a is None and b is None:
        return float(default)
    if a is None:
        return float((default + b) / 2.0)
    if b is None:
        return float((a + default) / 2.0)
    return float((a + b) / 2.0)


def _has_spread(samples: List[Dict[str, Any]]) -> bool:
    labels = {s.get('label') for s in samples if s.get('label') in LABELS}
    return len([l for l in labels if l]) >= 3


def compute_personal_thresholds(user_id: str) -> Dict[str, Any]:
    """Recompute and persist per-user thresholds using robust medians + EMA.

    Returns the updated thresholds.
    """
    db = _load_db()
    u = _get_user(db, user_id)
    samples: List[Dict[str, Any]] = u.get('samples', [])
    # Count valid samples (both AU and label present)
    valid = [s for s in samples if s.get('au') is not None and s.get('label') in LABELS]
    n_valid = len(valid)
    if n_valid < MIN_TOTAL_SAMPLES or not _has_spread(valid):
        # Not enough data; keep defaults/current
        if not u.get('thresholds'):
            u['thresholds'] = dict(DEFAULT_THRESHOLDS)
        _save_db(db)
        return u['thresholds']

    # Collect AU lists per label (robust clipped)
    per_label: Dict[str, List[float]] = {k: [] for k in LABELS}
    for s in valid:
        au = s.get('au')
        lab = s.get('label')
        if au is None or lab not in LABELS:
            continue
        try:
            per_label[lab].append(float(au))
        except Exception:
            pass
    med = {lab: _median(_clipped(per_label.get(lab, []))) for lab in LABELS}

    # Build candidate boundaries from medians; fall back to defaults
    d = DEFAULT_THRESHOLDS
    b1 = _midpoint(med.get('无'), med.get('低'), d['b1'])
    b2 = _midpoint(med.get('低'), med.get('中'), d['b2'])
    b3 = _midpoint(med.get('中'), med.get('高'), d['b3'])
    b4 = _midpoint(med.get('高'), med.get('极高'), d['b4'])

    # Ensure ordering; if violated, softly project to increasing sequence
    cand = [b1, b2, b3, b4]
    for i in range(1, 4):
        if cand[i] <= cand[i - 1]:
            cand[i] = cand[i - 1] + 10.0

    # Shrinkage toward defaults based on sample size
    alpha = min(1.0, max(0.0, n_valid / float(SHRINK_FULL_AT)))
    d = DEFAULT_THRESHOLDS
    shrunk = [
        (1 - alpha) * float(d['b1']) + alpha * cand[0],
        (1 - alpha) * float(d['b2']) + alpha * cand[1],
        (1 - alpha) * float(d['b3']) + alpha * cand[2],
        (1 - alpha) * float(d['b4']) + alpha * cand[3],
    ]

    # EMA smoothing vs previous thresholds
    prev = u.get('thresholds') or d
    out = {
        'b1': EMA_BETA * float(prev.get('b1', d['b1'])) + (1 - EMA_BETA) * shrunk[0],
        'b2': EMA_BETA * float(prev.get('b2', d['b2'])) + (1 - EMA_BETA) * shrunk[1],
        'b3': EMA_BETA * float(prev.get('b3', d['b3'])) + (1 - EMA_BETA) * shrunk[2],
        'b4': EMA_BETA * float(prev.get('b4', d['b4'])) + (1 - EMA_BETA) * shrunk[3],
        'version': int(prev.get('version', 1)) + 1,
    }
    u['thresholds'] = out
    u['updated_at'] = _today_str()
    _save_db(db)
    return out


def get_user_thresholds(user_id: str) -> Dict[str, Any]:
    db = _load_db()
    u = _get_user(db, user_id)
    return u.get('thresholds') or dict(DEFAULT_THRESHOLDS)


def map_au_to_label(user_id: str, au: float) -> str:
    t = get_user_thresholds(user_id)
    b1, b2, b3, b4 = float(t['b1']), float(t['b2']), float(t['b3']), float(t['b4'])
    x = float(au)
    if x < b1:
        return '无'
    if x < b2:
        return '低'
    if x < b3:
        return '中'
    if x < b4:
        return '高'
    return '极高'


def map_label_to_au(user_id: str, label: str) -> float:
    """Return a typical AU value for a label under personalized thresholds.

    Uses interval midpoint as a robust typical value.
    """
    t = get_user_thresholds(user_id)
    b1, b2, b3, b4 = float(t['b1']), float(t['b2']), float(t['b3']), float(t['b4'])
    if label == '无':
        return max(0.0, b1 * 0.5)
    if label == '低':
        return (b1 + b2) / 2.0
    if label == '中':
        return (b2 + b3) / 2.0
    if label == '高':
        return (b3 + b4) / 2.0
    if label == '极高':
        return b4 + 50.0
    return (b2 + b3) / 2.0


def bandit_adjust_thresholds(user_id: str) -> Optional[Dict[str, Any]]:
    """Very conservative epsilon-greedy nudge of thresholds based on recent mismatch.

    - Look at recent BANDIT_WINDOW samples where both AU and label are present.
    - Compute mismatch rate between user label and map_au_to_label(au).
    - If mismatch > 0.35, nudge all boundaries up or down by BANDIT_STEP toward
      reducing error (heuristic: if AU->label tends to be lower than user label,
      nudge down; else nudge up). Cooldown COOLDOWN_DAYS between adjustments.

    Returns updated thresholds if changed, else None.
    """
    db = _load_db()
    u = _get_user(db, user_id)
    samples: List[Dict[str, Any]] = [s for s in u.get('samples', []) if s.get('au') is not None and s.get('label') in LABELS]
    if len(samples) < 10:
        return None
    recent = samples[-BANDIT_WINDOW:]
    if not recent:
        return None
    mismatches = 0
    bias = 0  # +1 means AU->label > user_label, -1 means lower
    rank = {lab: i for i, lab in enumerate(LABELS)}
    for s in recent:
        au = float(s['au'])
        ulabel = s['label']
        plabel = map_au_to_label(user_id, au)
        if plabel != ulabel:
            mismatches += 1
        bias += (1 if rank[plabel] > rank[ulabel] else (-1 if rank[plabel] < rank[ulabel] else 0))
    rate = mismatches / max(1, len(recent))
    if rate <= 0.35:
        return None

    # Cooldown by last updated date
    try:
        last = u.get('updated_at')
        if last:
            last_dt = datetime.strptime(last, '%Y-%m-%d')
            if (datetime.now() - last_dt).days < COOLDOWN_DAYS:
                return None
    except Exception:
        pass

    d = DEFAULT_THRESHOLDS
    th = u.get('thresholds') or d
    step = BANDIT_STEP if bias > 0 else (-BANDIT_STEP if bias < 0 else 0.0)
    if step == 0.0:
        return None
    new = {
        'b1': max(0.0, float(th.get('b1', d['b1'])) + step),
        'b2': max(0.0, float(th.get('b2', d['b2'])) + step),
        'b3': max(0.0, float(th.get('b3', d['b3'])) + step),
        'b4': max(0.0, float(th.get('b4', d['b4'])) + step),
        'version': int(th.get('version', 1)) + 1,
    }
    # keep ordering
    if not (new['b1'] < new['b2'] < new['b3'] < new['b4']):
        return None
    u['thresholds'] = new
    u['updated_at'] = _today_str()
    _save_db(db)
    return new


__all__ = [
    'add_training_sample',
    'compute_personal_thresholds',
    'get_user_thresholds',
    'map_au_to_label',
    'map_label_to_au',
    'bandit_adjust_thresholds',
]
