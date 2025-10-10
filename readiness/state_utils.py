from __future__ import annotations

from typing import Any, Optional

from readiness.state import ReadinessState


def create_state(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    gender: Optional[str] = None,
) -> ReadinessState:
    """Return a freshly initialised ReadinessState without touching existing APIs."""
    state = ReadinessState()
    if user_id is not None:
        state.raw_inputs.user_id = user_id
    if date is not None:
        state.raw_inputs.date = date
    if gender is not None:
        state.raw_inputs.gender = gender
    return state


def state_to_json(state: ReadinessState, **dump_kwargs: Any) -> str:
    """Serialize a ReadinessState to JSON for downstream agents."""
    return state.model_dump_json(**dump_kwargs)


__all__ = ["create_state", "state_to_json"]
