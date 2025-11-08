#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class TrainingSession(TypedDict, total=False):
    session_id: str
    rpe: int
    duration_minutes: int
    label: str  # 极高/高/中/低/休息
    au: float
    start_time: str


class TrainingConsumptionInput(TypedDict, total=False):
    user_id: str
    date: str  # YYYY-MM-DD
    base_readiness_score: int
    training_sessions: List[TrainingSession]
    journal: Dict[str, Any]
    device_metrics: Dict[str, Any]
    params_override: Dict[str, Any]


class TrainingSessionResult(TypedDict, total=False):
    session_id: str
    au_used: float
    label_used: Optional[str]
    delta_consumption: float


class TrainingConsumptionOutput(TypedDict, total=False):
    user_id: str
    date: str
    base_readiness_score: int
    consumption_score: float
    display_readiness: int
    breakdown: Dict[str, float]
    sessions: List[TrainingSessionResult]
    caps_applied: Dict[str, float]
    params_used: Dict[str, Any]


__all__ = [
    "TrainingSession",
    "TrainingConsumptionInput",
    "TrainingSessionResult",
    "TrainingConsumptionOutput",
]

