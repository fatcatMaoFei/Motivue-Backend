#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional

_REGISTRY: Dict[str, Dict[str, float]] = {}


def set_user_cycle_params(user_id: str, ov_frac: float, luteal_off: float, sig_scale: float) -> None:
    _REGISTRY[user_id] = {
        'ov_frac': float(ov_frac),
        'luteal_off': float(luteal_off),
        'sig_scale': float(sig_scale),
    }


def get_user_cycle_params(user_id: str) -> Optional[Dict[str, float]]:
    return _REGISTRY.get(user_id)

