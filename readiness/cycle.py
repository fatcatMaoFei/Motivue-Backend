from __future__ import annotations

from math import exp
from typing import Dict


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def _gauss(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return exp(-0.5 * z * z)


def cycle_likelihood_by_day(day: int, cycle_length: int = 28) -> Dict[str, float]:
    """Compute a smooth likelihood P(E|State) vector from menstrual cycle day.

    Design (heuristic, smooth, continuous):
    - Ovulation window (~mid-cycle) favors Peak/Well-adapted via Gaussian peak.
    - Late luteal (pre-menses) favors NFOR/Acute via Gaussian near cycle end.
    - Early menses (days 1-3) adds mild Acute component.
    - FOR acts as a moderate band across cycle (broader sigma).
    - OTS remains minimal baseline.
    """
    # Robust bounds
    L = max(20, min(40, int(cycle_length or 28)))
    d = max(1, min(L, int(day or 1)))

    # Centers (relative to cycle length)
    ov = 0.5 * L                 # ovulation approx mid-cycle
    luteal_late = L - 2          # late luteal/pre-menses center
    menses_early = 2             # menses early center (day 1-3)

    # Sigmas (tunable)
    sig_peak = 2.2
    sig_well = 3.2
    sig_nfor = 2.5
    sig_acute = 2.8
    sig_for = 5.0

    # Raw components
    g_peak = _gauss(d, ov, sig_peak)
    g_well = _gauss(d, ov, sig_well)
    g_nfor = _gauss(d, luteal_late, sig_nfor)
    g_acute_late = _gauss(d, luteal_late - 2.0, sig_acute)
    g_acute_early = _gauss(d, menses_early, sig_acute)
    g_for = _gauss(d, 0.35 * L, sig_for) + _gauss(d, 0.65 * L, sig_for)

    # Combine into states (weights sum arbitrary then normalized)
    raw = {
        'Peak': 0.85 * g_peak + 0.15 * g_well,
        'Well-adapted': 0.70 * g_well + 0.20 * g_peak + 0.10 * g_for,
        'FOR': 0.60 * g_for + 0.20 * g_well + 0.20 * g_acute_early,
        'Acute Fatigue': 0.55 * g_acute_late + 0.35 * g_acute_early + 0.10 * g_for,
        'NFOR': 0.70 * g_nfor + 0.25 * g_acute_late + 0.05 * g_for,
        'OTS': 1e-6,
    }

    # Normalize and floor
    eps = 1e-6
    s = sum(max(v, eps) for v in raw.values())
    return {k: max(v, eps) / s for k, v in raw.items()}


def cycle_like_params(day: int, L: int, ov_frac: float, luteal_off: float, sig_scale: float) -> Dict[str, float]:
    """Parameterized cycle likelihood for personalization.
    - ov_frac: ovulation center as fraction of cycle length (e.g., 0.50)
    - luteal_off: shift (days) for late-luteal center relative to L-2
    - sig_scale: multiplies base sigmas
    """
    L = max(20, min(40, int(L or 28)))
    d = max(1, min(L, int(day or 1)))
    ov = max(1.0, min(L * 0.9, ov_frac * L))
    luteal_late = max(1.0, min(L * 1.0, (L - 2) + luteal_off))
    menses_early = 2.0

    sig_peak = 2.2 * sig_scale
    sig_well = 3.2 * sig_scale
    sig_nfor = 2.5 * sig_scale
    sig_acute = 2.8 * sig_scale
    sig_for = 5.0 * sig_scale

    g_peak = _gauss(d, ov, sig_peak)
    g_well = _gauss(d, ov, sig_well)
    g_nfor = _gauss(d, luteal_late, sig_nfor)
    g_acute_late = _gauss(d, luteal_late - 2.0, sig_acute)
    g_acute_early = _gauss(d, menses_early, sig_acute)
    g_for = _gauss(d, 0.35 * L, sig_for) + _gauss(d, 0.65 * L, sig_for)

    raw = {
        'Peak': 0.85 * g_peak + 0.15 * g_well,
        'Well-adapted': 0.70 * g_well + 0.20 * g_peak + 0.10 * g_for,
        'FOR': 0.60 * g_for + 0.20 * g_well + 0.20 * g_acute_early,
        'Acute Fatigue': 0.55 * g_acute_late + 0.35 * g_acute_early + 0.10 * g_for,
        'NFOR': 0.70 * g_nfor + 0.25 * g_acute_late + 0.05 * g_for,
        'OTS': 1e-6,
    }
    eps = 1e-6
    s = sum(max(v, eps) for v in raw.values())
    return {k: max(v, eps) / s for k, v in raw.items()}



__all__ = ['cycle_likelihood_by_day']
