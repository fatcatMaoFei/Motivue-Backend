"""Baseline analytics: windowed comparisons for daily metrics.

Exports two decoupled helpers:
- daily_vs_baseline.compare_today_vs_baseline: today vs N‑day window baseline
- periodic_review.compare_recent_vs_previous: recent N vs previous N

Both functions are pure and do not depend on readiness mapping.
"""

from .daily_vs_baseline import compare_today_vs_baseline
from .periodic_review import compare_recent_vs_previous

__all__ = [
    "compare_today_vs_baseline",
    "compare_recent_vs_previous",
]

