#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simulate N days of readiness with simple, logical patterns.

Generates daily payloads with:
- Training load pattern (heavier days → next day higher Hooper fatigue/soreness)
- Occasional alcohol and late caffeine (short-term journal)
- Stepwise posterior updates via readiness.service

Outputs:
- CSV summary with date, training load, Hooper scores, journal, score, diagnosis
- JSONL payloads for reproducibility

Run examples:
  python -m readiness.simulate_days_via_service --days 10 --start 2025-09-01 --user u_sim
  python -m readiness.simulate_days_via_service --days 30 --start 2025-09-01 --user u_sim
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from readiness.service import compute_readiness_from_payload
from readiness.constants import TRAINING_LOAD_CPT


# ----------------------------- Utilities -----------------------------

DATE_FMT = "%Y-%m-%d"


def dt(s: str) -> datetime:
    return datetime.strptime(s, DATE_FMT)


def ds(d: datetime) -> str:
    return d.strftime(DATE_FMT)


def heaviness_score(cpt_row: Dict[str, float]) -> float:
    """Heaviness proxy from training CPT row (higher → heavier training).
    Use states that represent fatigue/overreaching.
    """
    return (
        float(cpt_row.get('Acute Fatigue', 0.0))
        + 0.8 * float(cpt_row.get('FOR', 0.0))
        + 1.2 * float(cpt_row.get('NFOR', 0.0))
    )


def choose_training_sequence(keys: List[str], days: int, rng: random.Random) -> List[str]:
    """Create a plausible training load plan mixing heavy/moderate/light days.
    Picks based on heaviness derived from constants.
    """
    # Rank keys by heaviness from CPT
    ranked = sorted(keys, key=lambda k: heaviness_score(TRAINING_LOAD_CPT[k]), reverse=True)
    heavy = ranked[0]
    mid = ranked[min(1, len(ranked) - 1)] if len(ranked) > 1 else ranked[0]
    light = ranked[-1]

    seq: List[str] = []
    # Simple mesocycle: 3-on-1-off style with occasional tweaks
    i = 0
    while len(seq) < days:
        block = [mid, heavy, mid, light]
        # Occasionally push a second heavy in a block
        if rng.random() < 0.30:
            block[2] = heavy
        # Occasionally make a full recovery day (double light)
        if rng.random() < 0.20:
            block[3] = light
        for x in block:
            if len(seq) < days:
                seq.append(x)
            else:
                break
        i += 4
    return seq


def clamp(x: int, lo: int = 1, hi: int = 7) -> int:
    return max(lo, min(hi, x))


@dataclass
class DayContext:
    date: str
    training_load: str
    hooper_fatigue: int
    hooper_soreness: int
    hooper_stress: int
    hooper_sleep: int
    alcohol: bool
    late_caffeine: bool
    screen_before_bed: bool
    late_meal: bool
    is_sick: bool
    is_injured: bool
    readiness_score: Optional[float] = None
    diagnosis: Optional[str] = None


def generate_day_contexts(
    start_date: str,
    days: int,
    rng: random.Random,
) -> List[DayContext]:
    keys = list(TRAINING_LOAD_CPT.keys())
    if not keys:
        raise RuntimeError("TRAINING_LOAD_CPT is empty; cannot simulate.")

    training_seq = choose_training_sequence(keys, days, rng)

    contexts: List[DayContext] = []
    start = dt(start_date)

    # Pre-compute heaviness rank for conditional Hooper generation
    ranked = sorted(keys, key=lambda k: heaviness_score(TRAINING_LOAD_CPT[k]), reverse=True)
    heavy_keys = set(ranked[: max(1, len(ranked) // 3)])  # top ~1/3 as heavy

    for i in range(days):
        d = ds(start + timedelta(days=i))
        tl_today = training_seq[i]

        # Yesterday context to affect today's Hooper
        tl_yday = training_seq[i - 1] if i > 0 else None
        yday_heavy = tl_yday in heavy_keys if tl_yday is not None else False

        # Baseline Hooper near low values; increase if yesterday heavy or alcohol
        base_fatigue = rng.randint(1, 3)
        base_soreness = rng.randint(1, 3)
        base_stress = rng.randint(1, 3)
        base_sleep = rng.randint(1, 3)

        # Journals for yesterday that influence today prior (short-term)
        # Frequency heuristics: alcohol ~1-2 / week; late caffeine ~1 / week; screens ~2 / week; late meal ~1 / week
        alcohol = rng.random() < 0.18
        late_caffeine = rng.random() < 0.12
        screen_before_bed = rng.random() < 0.28
        late_meal = rng.random() < 0.14

        # Persistent items rare
        is_sick = rng.random() < 0.03
        is_injured = rng.random() < 0.02

        # Effects carry into today's Hooper
        if yday_heavy:
            base_fatigue += 2
            base_soreness += 2
            base_stress += 1
            base_sleep += 1
        if alcohol:
            base_fatigue += 1
            base_sleep += 1
        if late_caffeine or screen_before_bed:
            base_sleep += 1
        if is_sick:
            base_fatigue += 1
            base_stress += 1

        ctx = DayContext(
            date=d,
            training_load=tl_today,
            hooper_fatigue=clamp(base_fatigue),
            hooper_soreness=clamp(base_soreness),
            hooper_stress=clamp(base_stress),
            hooper_sleep=clamp(base_sleep),
            alcohol=alcohol,
            late_caffeine=late_caffeine,
            screen_before_bed=screen_before_bed,
            late_meal=late_meal,
            is_sick=is_sick,
            is_injured=is_injured,
        )
        contexts.append(ctx)

    return contexts


def run_simulation(
    user_id: str,
    start_date: str,
    days: int,
    out_prefix: Path,
    rng_seed: int = 42,
) -> Tuple[List[DayContext], List[Dict[str, Any]]]:
    rng = random.Random(rng_seed)
    ctxs = generate_day_contexts(start_date=start_date, days=days, rng=rng)

    results: List[Dict[str, Any]] = []
    prev_probs: Optional[Dict[str, float]] = None

    # Track recent training loads for streak effect
    recent_loads: List[str] = []

    for i, ctx in enumerate(ctxs):
        payload: Dict[str, Any] = {
            'user_id': user_id,
            'date': ctx.date,
            'gender': '男',
            'previous_state_probs': prev_probs,
            'training_load': ctx.training_load,
            'recent_training_loads': list(recent_loads[-8:]),
            'journal': {
                # Short-term (apply to yesterday prior inside service)
                'alcohol_consumed': ctx.alcohol,
                'late_caffeine': ctx.late_caffeine,
                'screen_before_bed': ctx.screen_before_bed,
                'late_meal': ctx.late_meal,
                # Persistent (apply to today posterior)
                'is_sick': ctx.is_sick,
                'is_injured': ctx.is_injured,
            },
            'hooper': {
                'fatigue': ctx.hooper_fatigue,
                'soreness': ctx.hooper_soreness,
                'stress': ctx.hooper_stress,
                'sleep': ctx.hooper_sleep,
            },
        }

        res = compute_readiness_from_payload(payload)
        ctx.readiness_score = float(res.get('final_readiness_score'))
        ctx.diagnosis = str(res.get('final_diagnosis'))
        results.append(res)

        # Prepare chaining for next day
        prev_probs = res.get('next_previous_state_probs')
        recent_loads.append(ctx.training_load)

    # Write outputs
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    csv_path = out_prefix.with_suffix('.csv')
    with csv_path.open('w', encoding='utf-8') as f:
        f.write('date,training_load,fatigue_hooper,soreness_hooper,stress_hooper,sleep_hooper,'
                'alcohol,late_caffeine,screen_before_bed,late_meal,is_sick,is_injured,score,diagnosis\n')
        for c in ctxs:
            f.write(','.join([
                c.date,
                str(c.training_load),
                str(c.hooper_fatigue),
                str(c.hooper_soreness),
                str(c.hooper_stress),
                str(c.hooper_sleep),
                '1' if c.alcohol else '0',
                '1' if c.late_caffeine else '0',
                '1' if c.screen_before_bed else '0',
                '1' if c.late_meal else '0',
                '1' if c.is_sick else '0',
                '1' if c.is_injured else '0',
                f"{c.readiness_score if c.readiness_score is not None else ''}",
                f"{c.diagnosis if c.diagnosis is not None else ''}",
            ]) + '\n')

    jsonl_path = out_prefix.with_suffix('.jsonl')
    with jsonl_path.open('w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    return ctxs, results


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=30, help='Number of days to simulate (e.g., 10 or 30)')
    ap.add_argument('--start', type=str, default=datetime.now().strftime(DATE_FMT), help='Start date YYYY-MM-DD')
    ap.add_argument('--user', type=str, default='u_sim', help='User ID for the simulation')
    ap.add_argument('--seed', type=int, default=42, help='Random seed')
    ap.add_argument('--out', type=str, default='readiness/examples/sim_user', help='Output prefix path (without extension)')
    args = ap.parse_args(argv)

    out_prefix = Path(args.out).with_name(f"{Path(args.out).name}_{args.days}d")
    ctxs, _ = run_simulation(user_id=args.user, start_date=args.start, days=args.days, out_prefix=out_prefix, rng_seed=args.seed)

    # Console summary
    scores = [c.readiness_score for c in ctxs if c.readiness_score is not None]
    if scores:
        lo, hi = min(scores), max(scores)
        avg = sum(scores) / len(scores)
        print(f"Days={args.days}  Score min/avg/max = {lo:.1f}/{avg:.1f}/{hi:.1f}")
    else:
        print("No scores computed.")

    # Quick plausibility check: mean Hooper after heavy-yesterday vs others
    # Identify heavy days via TRAINING_LOAD_CPT heaviness rank (same as generator)
    keys = list(TRAINING_LOAD_CPT.keys())
    ranked = sorted(keys, key=lambda k: heaviness_score(TRAINING_LOAD_CPT[k]), reverse=True)
    heavy_keys = set(ranked[: max(1, len(ranked) // 3)])

    means_after_heavy: List[float] = []
    means_other: List[float] = []
    for i in range(1, len(ctxs)):
        mean_hooper = (ctxs[i].hooper_fatigue + ctxs[i].hooper_soreness + ctxs[i].hooper_stress + ctxs[i].hooper_sleep) / 4.0
        if ctxs[i - 1].training_load in heavy_keys:
            means_after_heavy.append(mean_hooper)
        else:
            means_other.append(mean_hooper)
    if means_after_heavy and means_other:
        ah = sum(means_after_heavy) / len(means_after_heavy)
        ot = sum(means_other) / len(means_other)
        print(f"Mean Hooper after heavy-yesterday = {ah:.2f}; others = {ot:.2f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

