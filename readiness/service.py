"""Service interface for the Readiness model.

Provides a single function `compute_readiness_from_payload` that accepts a
unified JSON-like dict and returns readiness results. This mirrors and replaces
the standalone readiness_service.py script.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from readiness.engine import ReadinessEngine


def compute_readiness_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = payload.get('user_id') or 'default_user'
    date = payload.get('date') or '1970-01-01'
    gender = payload.get('gender') or '男性'
    prev_probs = payload.get('previous_state_probs')

    manager = ReadinessEngine(
        user_id=user_id,
        date=date,
        previous_state_probs=prev_probs,
        gender=gender,
    )

    causal_inputs: Dict[str, Any] = {}
    if payload.get('training_load') is not None:
        causal_inputs['training_load'] = payload['training_load']
    if isinstance(payload.get('recent_training_loads'), list):
        causal_inputs['recent_training_loads'] = payload['recent_training_loads']
    # Optional recent AU series (preferred for ACWR/Fatigue_3day when provided)
    if isinstance(payload.get('recent_training_au'), list):
        causal_inputs['recent_training_au'] = payload['recent_training_au']
    # Optional auxiliaries for Fatigue_3day normalization and symptoms
    if payload.get('au_norm_ref') is not None:
        causal_inputs['au_norm_ref'] = payload.get('au_norm_ref')
    if payload.get('doms_nrs') is not None:
        causal_inputs['doms_nrs'] = payload.get('doms_nrs')
    if payload.get('energy_nrs') is not None:
        causal_inputs['energy_nrs'] = payload.get('energy_nrs')

    # Optional: persist WHOOP Journal items (raw, not used in daily computation)
    if isinstance(payload.get('whoop_journal'), dict):
        manager.journal_manager.add_journal_entry(user_id, date, 'whoop_journal', payload['whoop_journal'])

    # Unified journal support (simple and robust):
    # - Short-term items (alcohol/late_caffeine/screen_before_bed/late_meal) → act on TODAY prior; write into YESTERDAY store
    # - Persistent items (is_sick/is_injured/high_stress_event_today/meditation_done_today) → act on TODAY posterior; write into TODAY store
    journal = payload.get('journal') or {}
    # Journal classification (computation defaults):
    # - Persistent (carry into today's posterior until explicitly turned off): only is_sick, is_injured
    # - Short-term (affect today's prior, then auto-clear tomorrow): alcohol/late_caffeine/screen/late_meal
    #   plus other app-defined keys (e.g., high_stress_event_today, meditation_done_today) if present; they are
    #   stored but, unless whitelisted by engine CPTs, do not affect computation and will be auto-cleared.
    short_term_keys = [
        'alcohol_consumed', 'late_caffeine', 'screen_before_bed', 'late_meal',
        'high_stress_event_today', 'meditation_done_today'
    ]
    persistent_keys = ['is_sick', 'is_injured']

    short_term_from_unified = {k: v for k, v in journal.items() if k in short_term_keys and v is not None}
    persistent_from_unified = {k: v for k, v in journal.items() if k in persistent_keys and v is not None}
    # Any other custom keys default to short-term: saved for record + auto-cleared next day; no computation impact unless later whitelisted
    custom_other = {k: v for k, v in journal.items() if v is not None and k not in short_term_keys and k not in persistent_keys}

    # Backward compatibility: also accept journal_yesterday / journal_today if provided
    journal_yesterday = payload.get('journal_yesterday') or {}
    journal_today = payload.get('journal_today') or {}

    # Merge unified into specific
    short_term_all = {**short_term_from_unified, **custom_other, **journal_yesterday}
    persistent_all = {**persistent_from_unified, **journal_today}

    if short_term_all:
        from datetime import datetime, timedelta
        y_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        manager.journal_manager.add_journal_entry(user_id, y_date, 'short_term_behaviors', short_term_all)

    if persistent_all:
        manager.journal_manager.add_journal_entry(user_id, date, 'persistent_status', persistent_all)

    # Compute prior after journaling yesterday's short-term behaviors
    prior = manager.calculate_today_prior(causal_inputs)

    # Optional menstrual cycle as posterior evidence (from HealthKit)
    cycle = payload.get('cycle') or {}

    objective = payload.get('objective') or {}
    hooper = payload.get('hooper') or {}

    # Hooper mapping
    hooper_mapped = {}
    if 'fatigue' in hooper: hooper_mapped['fatigue_hooper'] = hooper['fatigue']
    if 'soreness' in hooper: hooper_mapped['soreness_hooper'] = hooper['soreness']
    if 'stress' in hooper: hooper_mapped['stress_hooper'] = hooper['stress']
    if 'sleep' in hooper: hooper_mapped['sleep_hooper'] = hooper['sleep']

    # Stepwise updates
    if objective:
        manager.add_evidence_and_update(objective)
    if hooper_mapped:
        manager.add_evidence_and_update(hooper_mapped)
    # Menstrual cycle evidence (posterior, continuous)
    if cycle:
        manager.add_evidence_and_update({'cycle': cycle})
    # Today's journal evidence is read from JournalManager inside the engine
    if persistent_all:
        manager.add_evidence_and_update({})

    # Auto-clearing of short-term is done inside engine after applying yesterday's journal.

    summary = manager.get_daily_summary()
    return {
        'user_id': user_id,
        'date': date,
        'gender': gender,
        'prior_probs': summary['prior_probs'],
        'final_posterior_probs': summary['final_posterior_probs'],
        'final_readiness_score': summary['final_readiness_score'],
        'final_diagnosis': summary['final_diagnosis'],
        'update_history': summary['update_history'],
        'evidence_pool': summary['evidence_pool'],
        'next_previous_state_probs': summary['final_posterior_probs'],
    }

__all__ = ['compute_readiness_from_payload']
