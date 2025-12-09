"""Service interface for the Readiness model.

Provides a single function `compute_readiness_from_payload` that accepts a
unified JSON-like dict and returns readiness results. This mirrors and replaces
the standalone readiness_service.py script.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from readiness.engine import ReadinessEngine
from readiness.constants import TRAINING_LOAD_AU


def _au_to_label_by_nearest(au: float) -> str:
    """Map numeric AU to the nearest discrete training_load label."""
    best_label: Optional[str] = None
    best_dist: Optional[float] = None
    for lbl, val in TRAINING_LOAD_AU.items():
        try:
            v = float(val)
            d = abs(float(au) - v)
        except Exception:
            continue
        if best_dist is None or d < best_dist:
            best_label, best_dist = lbl, d
    return best_label or "中"


def compute_readiness_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main entrypoint used by API and tools.

    This wrapper is intentionally skinny: it normalizes inputs, prepares the
    causal and evidence dictionaries, and delegates all math to ReadinessEngine.

    NOTE: As of this version we deliberately exclude:
      - journal behaviours (alcohol/late caffeine/screen/late_meal)
      - disease / injury flags
      - Apple sleep score
      - Nutrition & GI enums
    from readiness computation. They may still be stored in JournalManager or
    upstream services for reporting purposes, but they no longer affect prior
    or posterior probabilities.
    """

    user_id = payload.get("user_id") or "default_user"
    date = payload.get("date") or "1970-01-01"
    gender = payload.get("gender") or "男"
    prev_probs: Optional[Dict[str, float]] = payload.get("previous_state_probs")

    # Normalize gender default (fix potential encoding and empty values)
    try:
        g = gender
        if g is None or str(g).strip().lower() in ["", "none", "null", "nan"]:
            gender = "男"
    except Exception:
        gender = "男"

    # Optional per-user EMISSION_CPT override
    emission_override: Optional[Dict[str, Any]] = None
    if isinstance(payload.get("emission_cpt_override"), dict):
        emission_override = payload.get("emission_cpt_override")

    manager = ReadinessEngine(
        user_id=user_id,
        date=date,
        previous_state_probs=prev_probs,
        gender=gender,
        emission_cpt_override=emission_override,
    )

    # ------------------------ Training load mixing -------------------------
    # Device + manual training load:
    # - device_training_au: numeric AU from wearable aggregation
    # - manual_training_au: explicit AU from app (e.g. sum of RPE×duration)
    # - rpe / duration_minutes: fallback to compute manual AU if provided
    # - training_load_manual: manual label (极高/高/中/低/休) as last resort
    device_au = payload.get("device_training_au")

    manual_au: Optional[float] = None
    # 1) Explicit manual AU supplied by客户端
    if payload.get("manual_training_au") is not None:
        try:
            manual_au = float(payload.get("manual_training_au"))
        except Exception:
            manual_au = None

    # 2) RPE × duration (top-level)
    if manual_au is None:
        rpe = payload.get("rpe")
        dur = payload.get("duration_minutes")
        try:
            if rpe is not None and dur is not None:
                rpe_f = float(rpe)
                dur_f = float(dur)
                if rpe_f > 0 and dur_f > 0:
                    manual_au = rpe_f * dur_f
        except Exception:
            manual_au = None

    # 3) Manual label → AU
    if manual_au is None:
        manual_label = payload.get("training_load_manual") or payload.get("training_load")
        if isinstance(manual_label, str) and manual_label in TRAINING_LOAD_AU:
            try:
                manual_au = float(TRAINING_LOAD_AU[manual_label])
            except Exception:
                manual_au = None

    mixed_au: Optional[float] = None
    try:
        if device_au is not None and manual_au is not None:
            mixed_au = 0.5 * float(device_au) + 0.5 * float(manual_au)
        elif device_au is not None:
            mixed_au = float(device_au)
        elif manual_au is not None:
            mixed_au = float(manual_au)
    except Exception:
        mixed_au = None

    if mixed_au is not None:
        # If caller did not provide a training_load label, derive one from AU.
        payload["training_load"] = _au_to_label_by_nearest(mixed_au)
        # Extend recent_training_au with today's AU so ACWR can use it
        recent_au_seq = payload.get("recent_training_au")
        if isinstance(recent_au_seq, list):
            seq: list[float] = []
            try:
                seq = [float(x) for x in recent_au_seq]
            except Exception:
                seq = []
            seq.append(mixed_au)
            payload["recent_training_au"] = seq
        else:
            payload["recent_training_au"] = [mixed_au]

    # ------------------------ Causal inputs (Prior) ------------------------
    causal_inputs: Dict[str, Any] = {}
    if payload.get("training_load") is not None:
        causal_inputs["training_load"] = payload["training_load"]
    if isinstance(payload.get("recent_training_loads"), list):
        causal_inputs["recent_training_loads"] = payload["recent_training_loads"]
    # Prefer explicit AU series when provided (for ACWR/Fatigue_3day)
    if isinstance(payload.get("recent_training_au"), list):
        causal_inputs["recent_training_au"] = payload["recent_training_au"]
    # Optional auxiliaries for Fatigue_3day normalization and symptoms
    if payload.get("au_norm_ref") is not None:
        causal_inputs["au_norm_ref"] = payload.get("au_norm_ref")
    if payload.get("doms_nrs") is not None:
        causal_inputs["doms_nrs"] = payload.get("doms_nrs")
    if payload.get("energy_nrs") is not None:
        causal_inputs["energy_nrs"] = payload.get("energy_nrs")

    # Optional: persist WHOOP Journal items (raw, not used in daily computation)
    if isinstance(payload.get("whoop_journal"), dict):
        manager.journal_manager.add_journal_entry(user_id, date, "whoop_journal", payload["whoop_journal"])

    # Unified journal payload（仅用于存档，不再参与 readiness 计算）
    journal = payload.get("journal") or {}
    if journal:
        manager.journal_manager.add_journal_entry(user_id, date, "journal", journal)

    # Legacy journal_yesterday / journal_today 同样作为存档
    if isinstance(payload.get("journal_yesterday"), dict):
        manager.journal_manager.add_journal_entry(user_id, date, "journal_yesterday", payload["journal_yesterday"])
    if isinstance(payload.get("journal_today"), dict):
        manager.journal_manager.add_journal_entry(user_id, date, "journal_today", payload["journal_today"])

    # Compute prior after preparing causal inputs
    prior = manager.calculate_today_prior(causal_inputs)

    # Optional menstrual cycle as posterior evidence (from HealthKit)
    cycle = payload.get("cycle") or {}

    # ---------------------- Objective / evidence inputs --------------------
    objective: Dict[str, Any] = dict(payload.get("objective") or {})

    # Accept top-level fields commonly sent by clients or CSV ingestion
    passthrough_keys = [
        # direct enums
        "sleep_performance_state",
        "restorative_sleep",
        "hrv_trend",
        "fatigue_3day_state",
        # numeric metrics that mapping can convert
        "sleep_duration_hours",
        "sleep_efficiency",
        "total_sleep_minutes",
        "restorative_ratio",
        "deep_sleep_ratio",
        "rem_sleep_ratio",
        "hrv_rmssd_today",
        "hrv_rmssd_3day_avg",
        "hrv_rmssd_7day_avg",
        "hrv_baseline_mu",
        "hrv_baseline_sd",
        "hrv_rmssd_28day_avg",
        "hrv_rmssd_28day_sd",
        "sleep_baseline_hours",
        "sleep_baseline_eff",
        "rest_baseline_ratio",
    ]
    for k in passthrough_keys:
        v = payload.get(k)
        if v is not None and k not in objective:
            objective[k] = v

    # Hooper mapping (1..7 -> low/medium/high by mapper)
    hooper = payload.get("hooper") or {}
    hooper_mapped: Dict[str, Any] = {}
    if "fatigue" in hooper:
        hooper_mapped["fatigue_hooper"] = hooper["fatigue"]
    if "soreness" in hooper:
        hooper_mapped["soreness_hooper"] = hooper["soreness"]
    if "stress" in hooper:
        hooper_mapped["stress_hooper"] = hooper["stress"]
    if "sleep" in hooper:
        hooper_mapped["sleep_hooper"] = hooper["sleep"]

    # Apple 睡眠评分暂不参与 readiness 引擎，只允许上游存档使用
    apple_sleep_score = payload.get("apple_sleep_score")
    ios_version = payload.get("ios_version")
    _ = (apple_sleep_score, ios_version)  # kept for potential upstream logging

    # ----------------------------- Updates ---------------------------------
    if objective:
        manager.add_evidence_and_update(objective)
    if hooper_mapped:
        manager.add_evidence_and_update(hooper_mapped)
    # Menstrual cycle evidence (posterior, continuous) with key unification
    if cycle:
        cy = dict(cycle)
        if "length" not in cy and "cycle_length" in cy and cy.get("cycle_length") is not None:
            cy["length"] = cy.get("cycle_length")
        manager.add_evidence_and_update({"cycle": cy})

    summary = manager.get_daily_summary()
    return {
        "user_id": user_id,
        "date": date,
        "gender": gender,
        "prior_probs": summary["prior_probs"],
        "final_posterior_probs": summary["final_posterior_probs"],
        "final_readiness_score": summary["final_readiness_score"],
        "final_diagnosis": summary["final_diagnosis"],
        "update_history": summary["update_history"],
        "evidence_pool": summary["evidence_pool"],
        "next_previous_state_probs": summary["final_posterior_probs"],
    }


__all__ = ["compute_readiness_from_payload"]
