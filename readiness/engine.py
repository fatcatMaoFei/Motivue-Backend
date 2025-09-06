"""Engine: Prior/Posterior computation entrypoints (decoupled from dynamic_model).

This module provides a self-contained engine that computes:
- Prior (yesterday->today baseline transition + causal factors + penalties)
- Posterior (accumulating evidence via EMISSION CPT, with evidence weights)

It depends only on readiness.constants and readiness.mapping.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, List

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
from readiness.mapping import map_inputs_to_states
from datetime import datetime, timedelta


class JournalManager:
    """In-memory journal store for short-term and persistent entries."""

    def __init__(self) -> None:
        self.journal_database: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _key(self, user_id: str, date: str) -> str:
        return f"{user_id}_{date}"

    def _get_previous_date(self, date_str: str) -> str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        previous_date = date_obj - timedelta(days=1)
        return previous_date.strftime("%Y-%m-%d")

    def get_yesterdays_journal(self, user_id: str, today_date: str) -> Dict[str, Any]:
        y_date = self._get_previous_date(today_date)
        return self.journal_database.get(self._key(user_id, y_date), {
            'short_term_behaviors': {},
            'persistent_status': {},
            'training_context': {}
        })

    def get_today_journal_evidence(self, user_id: str, date: str) -> Dict[str, Any]:
        key = self._key(user_id, date)
        today = self.journal_database.get(key, {})
        ev: Dict[str, Any] = {}
        persistent = today.get('persistent_status', {})
        short_term = today.get('short_term_behaviors', {})
        if persistent.get('is_sick'):
            ev['is_sick'] = True
        if persistent.get('is_injured'):
            ev['is_injured'] = True
        if persistent.get('high_stress_event_today'):
            ev['high_stress_event_today'] = True
        if short_term.get('meditation_done_today'):
            ev['meditation_done_today'] = True
        return ev

    def add_journal_entry(self, user_id: str, date: str, entry_type: str, entry_data: Dict[str, Any]) -> None:
        key = self._key(user_id, date)
        if key not in self.journal_database:
            self.journal_database[key] = {
                'short_term_behaviors': {},
                'persistent_status': {},
                'training_context': {},
                'whoop_journal': {},
                'daily_metrics': {},
            }
        self.journal_database[key][entry_type].update(entry_data)

    def auto_clear_short_term_flags(self, user_id: str, yesterday_date: str) -> None:
        key = self._key(user_id, yesterday_date)
        if key in self.journal_database:
            self.journal_database[key]['short_term_behaviors'] = {}


class ReadinessEngine:
    """Daily readiness engine with decoupled prior/posterior logic."""

    def __init__(self, user_id: str, date: str,
                 previous_state_probs: Optional[Dict[str, float]] = None,
                 gender: str = '男性') -> None:
        self.user_id = user_id
        self.date = date
        self.gender = gender
        self.states = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']

        self.previous_probs = previous_state_probs or {
            'Peak': 0.3, 'Well-adapted': 0.5, 'FOR': 0.15,
            'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0
        }

        self.journal_manager = JournalManager()
        self.today_prior_probs: Optional[Dict[str, float]] = None
        self.today_posterior_probs: Optional[Dict[str, float]] = None
        self.prior_calculated = False
        self.evidence_pool: Dict[str, Any] = {}
        self.update_history: List[Dict[str, Any]] = []

    # ---------- Prior ----------
    def calculate_today_prior(self, causal_inputs: Dict[str, Any]) -> Dict[str, float]:
        if self.prior_calculated:
            return self.today_prior_probs or {}

        # 1) Baseline transition P(Today|Yesterday)
        prior = {}
        for today_state in self.states:
            s = 0.0
            for y in self.states:
                s += self.previous_probs.get(y, 0.0) * BASELINE_TRANSITION_CPT[y].get(today_state, 1e-6)
            prior[today_state] = s
        prior = self._normalize(prior)

        # 2) Traditional causal inputs (training load, streak penalty)
        prior = self._apply_traditional_causal_inputs(prior, causal_inputs)

        # 3) Yesterday journal prior impacts (alcohol/screen/caffeine/late meal; sickness/injury; menstrual phase)
        y_journal = self.journal_manager.get_yesterdays_journal(self.user_id, self.date)
        if y_journal and any(y_journal.values()):
            training_load = causal_inputs.get('training_load', '中')
            # 昨日短期行为影响今日先验（酒精/咖啡因/屏幕/进食）
            prior = self._apply_journal_prior_impacts(prior, y_journal, training_load)
            # 持续状态（生病/受伤）按你的新规则：仅影响当日后验，不进入先验。
            # 但会自动“继承”到今天的 journal（可手动取消后重新计算）。
            carry = {}
            persistent = y_journal.get('persistent_status', {})
            if persistent.get('is_sick'):
                carry['is_sick'] = True
            if persistent.get('is_injured'):
                carry['is_injured'] = True
            if carry:
                self.journal_manager.add_journal_entry(self.user_id, self.date, 'persistent_status', carry)

        # 4) Auto-clear yesterday short-term flags
        y_date = self.journal_manager._get_previous_date(self.date)
        self.journal_manager.auto_clear_short_term_flags(self.user_id, y_date)

        self.today_prior_probs = prior
        self.today_posterior_probs = dict(prior)
        self.prior_calculated = True
        return prior

    def _apply_traditional_causal_inputs(self, probs: Dict[str, float], causal_inputs: Dict[str, Any]) -> Dict[str, float]:
        adjusted = dict(probs)
        # Training load
        if 'training_load' in causal_inputs:
            tl = causal_inputs['training_load']
            if tl in TRAINING_LOAD_CPT:
                adjusted = self._combine_probabilities_multiplicative(adjusted, TRAINING_LOAD_CPT[tl], CAUSAL_FACTOR_WEIGHTS.get('training_load', 1.0))
        # Streak penalty
        rtl = causal_inputs.get('recent_training_loads')
        if isinstance(rtl, list) and rtl:
            adjusted = self._apply_training_streak_penalty(adjusted, rtl)
        return adjusted

    def _apply_training_streak_penalty(self, probs: Dict[str, float], recent_training_loads: List[str]) -> Dict[str, float]:
        adjusted = dict(probs)
        HIGH = {'高', '极高'}
        loads = list(recent_training_loads or [])
        if len(loads) >= 4:
            last4 = loads[-4:]
            if sum(1 for x in last4 if x in HIGH) >= 3:
                adjusted = self._shift_probability(adjusted, ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue'], ['NFOR'], 0.50)
        if len(loads) >= 8:
            last8 = loads[-8:]
            if sum(1 for x in last8 if x in HIGH) >= 6:
                adjusted = self._shift_probability(adjusted, ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue'], ['NFOR'], 0.60)
        return adjusted

    def _apply_journal_prior_impacts(self, probs: Dict[str, float], journal_data: Dict[str, Any], training_load: str = '中') -> Dict[str, float]:
        adjusted = dict(probs)
        st = journal_data.get('short_term_behaviors', {})
        # Alcohol
        if st.get('alcohol_consumed'):
            adjusted = self._combine_probabilities_multiplicative(adjusted, ALCOHOL_CONSUMPTION_CPT[True], CAUSAL_FACTOR_WEIGHTS.get('alcohol', 1.0))
        # Late caffeine
        if st.get('late_caffeine'):
            adjusted = self._combine_probabilities_multiplicative(adjusted, LATE_CAFFEINE_CPT[True], CAUSAL_FACTOR_WEIGHTS.get('late_caffeine', 1.0))
        # Screen before bed
        if st.get('screen_before_bed'):
            adjusted = self._combine_probabilities_multiplicative(adjusted, SCREEN_BEFORE_BED_CPT[True], CAUSAL_FACTOR_WEIGHTS.get('screen_before_bed', 1.0))
        # Late meal: choose positive/negative by training load
        if st.get('late_meal'):
            positive = training_load in {'中', '高', '极高'}
            meal_key = 'positive' if positive else 'negative'
            adjusted = self._combine_probabilities_multiplicative(adjusted, LATE_MEAL_CPT[meal_key], CAUSAL_FACTOR_WEIGHTS.get('late_meal', 1.0))

        # Persistent: 按新规则，生病/受伤不进入先验；月经周期不进入先验（改为后验证据）
        # persistent = journal_data.get('persistent_status', {})
        return self._normalize(adjusted)

    # ---------- Posterior ----------
    def add_evidence_and_update(self, new_evidence: Dict[str, Any]) -> Dict[str, Any]:
        if not self.prior_calculated or self.today_prior_probs is None:
            raise RuntimeError('calculate_today_prior() must be called first')

        # 先合并今日 Journal 证据（自动继承的 is_sick/is_injured 也在其中），随后让新证据覆盖它们（支持“取消”）。
        today_ev = self.journal_manager.get_today_journal_evidence(self.user_id, self.date)
        if today_ev:
            for k, v in today_ev.items():
                self.evidence_pool[k] = v
        for k, v in new_evidence.items():
            if v is not None:
                self.evidence_pool[k] = v

        mapped = map_inputs_to_states(self.evidence_pool)
        self.today_posterior_probs = self._run_bayesian_update(self.today_prior_probs, mapped)

        score = self._get_readiness_score(self.today_posterior_probs)
        rec = {
            'timestamp': datetime.now().isoformat(),
            'new_evidence': dict(new_evidence),
            'evidence_pool_size': len(self.evidence_pool),
            'readiness_score': score,
            'posterior_probs': dict(self.today_posterior_probs),
        }
        self.update_history.append(rec)

        return {
            'readiness_score': score,
            'diagnosis': self._diagnosis(self.today_posterior_probs),
            'posterior_probs': self.today_posterior_probs,
            'evidence_pool_size': len(self.evidence_pool),
            'update_count': len(self.update_history),
        }

    def _run_bayesian_update(self, prior: Dict[str, float], evidence: Dict[str, Any]) -> Dict[str, float]:
        posterior = dict(prior)
        used_vars = set()

        # Prefer continuous Hooper mapping if numeric scores provided
        hooper_map = {
            'fatigue_hooper_score': 'subjective_fatigue',
            'soreness_hooper_score': 'muscle_soreness',
            'stress_hooper_score': 'subjective_stress',
            'sleep_hooper_score': 'subjective_sleep',
        }
        for score_key, model_var in hooper_map.items():
            if score_key in evidence and evidence[score_key] is not None:
                try:
                    from readiness.hooper import hooper_to_state_likelihood
                    score = int(evidence[score_key])
                    like_vec = hooper_to_state_likelihood(model_var, score)
                    w = float(EVIDENCE_WEIGHTS_FITNESS.get(model_var, 1.0))
                    for s in self.states:
                        posterior[s] = posterior.get(s, 0.0) * max(like_vec.get(s, 1e-6), 1e-6) ** w
                    used_vars.add(model_var)
                except Exception:
                    pass
        # Multiply by each categorical evidence likelihood with weights
        for var, val in evidence.items():
            # map to CPT var/level already done
            if var not in EMISSION_CPT:
                continue
            if val not in EMISSION_CPT[var]:
                continue
            if var in used_vars:
                # Skip categorical for vars already accounted by continuous Hooper
                continue
            like = EMISSION_CPT[var][val]
            w = float(EVIDENCE_WEIGHTS_FITNESS.get(var, 1.0))
            for s in self.states:
                posterior[s] = posterior.get(s, 0.0) * max(like.get(s, 1e-6), 1e-6) ** w

        # Interaction: soreness + stress
        if 'muscle_soreness' in evidence and 'subjective_stress' in evidence:
            k = (evidence['muscle_soreness'], evidence['subjective_stress'])
            if k in INTERACTION_CPT_SORENESS_STRESS:
                like2 = INTERACTION_CPT_SORENESS_STRESS[k]
                for s in self.states:
                    posterior[s] = posterior.get(s, 0.0) * max(like2.get(s, 1e-6), 1e-6)

        # Menstrual cycle as posterior (continuous) evidence
        if self.gender == '女性':
            day = None
            length = None
            # Accept either direct cycle_day/cycle_length or nested cycle dict in evidence
            if 'cycle_day' in evidence:
                try:
                    day = int(evidence.get('cycle_day'))
                except Exception:
                    day = None
                try:
                    length = int(evidence.get('cycle_length', 28))
                except Exception:
                    length = 28
            elif isinstance(evidence.get('cycle'), dict):
                cyc = evidence['cycle']
                try:
                    day = int(cyc.get('day'))
                except Exception:
                    day = None
                try:
                    length = int(cyc.get('length', 28))
                except Exception:
                    length = 28
            if day is not None:
                # Use per-user personalized params if available
                from readiness.cycle_personalization import get_user_cycle_params
                from readiness.cycle import cycle_likelihood_by_day, cycle_like_params
                params = get_user_cycle_params(self.user_id)
                if params:
                    like_vec = cycle_like_params(day, length or 28, params['ov_frac'], params['luteal_off'], params['sig_scale'])
                else:
                    like_vec = cycle_likelihood_by_day(day, length or 28)
                w = float(EVIDENCE_WEIGHTS_FITNESS.get('menstrual_cycle', 0.8))
                for s in self.states:
                    posterior[s] = posterior.get(s, 0.0) * max(like_vec.get(s, 1e-6), 1e-6) ** w

        return self._normalize(posterior)

    # ---------- Utils ----------
    def _normalize(self, probs: Dict[str, float]) -> Dict[str, float]:
        total = sum(probs.values())
        if total <= 0:
            n = len(self.states)
            return {s: 1.0 / n for s in self.states}
        return {s: probs.get(s, 0.0) / total for s in self.states}

    def _normalize_distribution(self, impact_cpt: Dict[str, float]) -> Dict[str, float]:
        eps = 1e-6
        clipped = {s: max(float(impact_cpt.get(s, eps)), eps) for s in self.states}
        t = sum(clipped.values())
        return {s: v / t for s, v in clipped.items()} if t > 0 else clipped

    def _combine_probabilities_multiplicative(self, current: Dict[str, float], impact_cpt: Dict[str, float], weight: float) -> Dict[str, float]:
        w = float(weight) if weight is not None else 1.0
        like = self._normalize_distribution(impact_cpt)
        out = {}
        for s in self.states:
            out[s] = current.get(s, 0.0) * max(like.get(s, 1e-6), 1e-6) ** w
        return self._normalize(out)

    def _shift_probability(self, probs: Dict[str, float], from_states: List[str], to_states: List[str], shift_ratio: float) -> Dict[str, float]:
        adjusted = dict(probs)
        total_from = sum(adjusted.get(s, 0.0) for s in from_states)
        amount = total_from * shift_ratio
        for s in from_states:
            if total_from > 0:
                reduction = (adjusted.get(s, 0.0) / total_from) * amount
                adjusted[s] = max(1e-6, adjusted.get(s, 0.0) - reduction)
        inc = amount / max(len(to_states), 1)
        for s in to_states:
            adjusted[s] = adjusted.get(s, 0.0) + inc
        return self._normalize(adjusted)

    def _get_readiness_score(self, probs: Dict[str, float]) -> int:
        score = sum(probs.get(s, 0.0) * READINESS_WEIGHTS.get(s, 0) for s in self.states)
        return int(round(score))

    def _diagnosis(self, probs: Dict[str, float]) -> str:
        return max(self.states, key=lambda s: probs.get(s, 0.0))

    def get_daily_summary(self) -> Dict[str, Any]:
        final_dx = self._diagnosis(self.today_posterior_probs or {})
        final_score = self._get_readiness_score(self.today_posterior_probs or {})
        return {
            'user_id': self.user_id,
            'date': self.date,
            'final_readiness_score': final_score,
            'final_diagnosis': final_dx,
            'final_posterior_probs': self.today_posterior_probs,
            'prior_probs': self.today_prior_probs,
            'evidence_pool': self.evidence_pool,
            'total_updates': len(self.update_history),
            'update_history': self.update_history,
        }

__all__ = ['ReadinessEngine', 'JournalManager']
