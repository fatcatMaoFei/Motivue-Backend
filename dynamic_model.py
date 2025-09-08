#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thin forwarder to the decoupled readiness package.

This file preserves the original import surface for backward compatibility,
while the actual implementation lives in `readiness.*`.

If you need the legacy full implementation, see `dynamic_model_backup.py`.
"""

from __future__ import annotations

from typing import Any, Dict

# Re-export constants/CPTs/weights
from readiness.constants import (
    EMISSION_CPT,
    INTERACTION_CPT_SORENESS_STRESS,
    BASELINE_TRANSITION_CPT,
    TRAINING_LOAD_CPT,
    ALCOHOL_CONSUMPTION_CPT,
    LATE_CAFFEINE_CPT,
    SCREEN_BEFORE_BED_CPT,
    LATE_MEAL_CPT,
    MENSTRUAL_PHASE_CPT,
    CAUSAL_FACTOR_WEIGHTS,
    READINESS_WEIGHTS,
    EVIDENCE_WEIGHTS_FITNESS,
)

# Engine classes
from readiness.engine import ReadinessEngine, JournalManager

# Mapping helper
from readiness.mapping import map_inputs_to_states


class DailyReadinessManager(ReadinessEngine):
    """Backward-compatible alias to the new engine."""

    pass


__all__ = [
    # Engine
    'DailyReadinessManager', 'JournalManager',
    # Mapping
    'map_inputs_to_states',
    # Constants/CPTs
    'EMISSION_CPT', 'INTERACTION_CPT_SORENESS_STRESS', 'BASELINE_TRANSITION_CPT',
    'TRAINING_LOAD_CPT', 'ALCOHOL_CONSUMPTION_CPT', 'LATE_CAFFEINE_CPT',
    'SCREEN_BEFORE_BED_CPT', 'LATE_MEAL_CPT', 'MENSTRUAL_PHASE_CPT',
    'CAUSAL_FACTOR_WEIGHTS', 'READINESS_WEIGHTS', 'EVIDENCE_WEIGHTS_FITNESS',
]

