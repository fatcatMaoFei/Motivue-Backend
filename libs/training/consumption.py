#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from .schemas import (
    TrainingConsumptionInput,
    TrainingConsumptionOutput,
)
from .factors import compute_training_consumption


DEFAULT_PARAMS = {
    "cap_session": 40.0,          # 单次训练最大消耗
    "cap_training_total": 60.0,   # 当日训练总消耗上限
    # 预留：未来非训练因子（alcohol/steps）的权重与上限
}


def _merge_params(override: Dict[str, Any] | None) -> Dict[str, Any]:
    p = dict(DEFAULT_PARAMS)
    if override:
        for k, v in override.items():
            p[k] = v
    return p


def calculate_consumption(payload: TrainingConsumptionInput) -> TrainingConsumptionOutput:
    """计算当日消耗分（仅训练因子，RPE 为主；不改 readiness 后验）。

    返回 display_readiness（若传入 base_readiness_score），便于前端直接显示：
      display = base_readiness_score - round(consumption_score)
    """
    user_id = str(payload.get("user_id", ""))
    date = str(payload.get("date", ""))
    base = int(payload.get("base_readiness_score", 0) or 0)
    sessions = list(payload.get("training_sessions", []) or [])
    params = _merge_params(payload.get("params_override"))

    total_training, session_results = compute_training_consumption(
        sessions=sessions,
        readiness_score=base,  # v1 不使用，仅预留
        cap_session=float(params["cap_session"]),
        cap_training_total=float(params["cap_training_total"]),
    )

    consumption = float(total_training)
    display = max(0, base - int(round(consumption))) if base else 0

    return {
        "user_id": user_id,
        "date": date,
        "base_readiness_score": base,
        "consumption_score": consumption,
        "display_readiness": display,
        "breakdown": {"training": consumption},
        "sessions": session_results,
        "caps_applied": {
            "cap_session": float(params["cap_session"]),
            "cap_training_total": float(params["cap_training_total"]),
        },
        "params_used": params,
    }


__all__ = ["calculate_consumption", "DEFAULT_PARAMS"]

