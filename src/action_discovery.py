"""Opt-in neural motor exploration and outcome-gated synapse discovery.

Motor babbling supplies occasional endogenous firing of *existing* motor
neurons. It does not choose a behaviour for the body: the shared
decision_engine.select_action still arbitrates competition, and probes can
lose to stronger innate urges.

Critically, a trial only teaches a sensor/drive -> motor synapse after the
causal ledger closes an outcome window for an actual attempted action.
Unrewarded poking cannot create an excitatory skill pathway. No action is
hard-wired to a condition or a reward in this module.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .brain_constants import (
    ACTION_BEHAVIOURS, ACTION_THRESHOLDS, CORE_STAT_NEURONS,
    LEARNED_ACTIONS, PURE_INPUT_NEURONS,
)
from .causal_learning import VALENCE_WEIGHTS

# Only voluntary, previously unwired motor neurons can be explored.
_EXPLORE_ACTIONS = tuple(x for x in LEARNED_ACTIONS if x in (
    "act_play", "act_shelter", "act_rest",
))
_BY_BEHAVIOUR = {ACTION_BEHAVIOURS[x]: x for x in _EXPLORE_ACTIONS}


@dataclass
class _Evidence:
    count: int = 0
    total_benefit: float = 0.0

    @property
    def mean(self):
        return self.total_benefit / self.count if self.count else 0.0


class ActionDiscovery:
    """Observe motor trials and strengthen consistently useful cue->action edges.

    This class is an *experimental* learning mechanism. It runs only when
    explicitly enabled by the headless training configuration. It must be
    evaluated against its own no-exploration/no-teaching controls before
    considering desktop or Android integration.
    """

    def __init__(self, brain, *, rate: float = 0.08, seed: int = 0,
                 trials_to_learn: int = 3, minimum_benefit: float = 0.025,
                 learning_step: float = 0.18, teaching: bool = True):
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be in [0, 1]")
        self.brain = brain
        self.rate = rate
        self.rng = random.Random(seed)
        self.trials_to_learn = max(2, int(trials_to_learn))
        self.minimum_benefit = float(minimum_benefit)
        self.learning_step = float(learning_step)
        self.teaching = bool(teaching)

        self.pending = {}  # episode_id -> (motor_neuron, copy of pre-action state)
        self.evidence: Dict[Tuple[str, str], _Evidence] = {}
        self.probes = 0
        self.executed_probes = 0
        self.trials_closed = 0
        self.connections_taught = 0
        self.aborted_trials = 0
        self._closed_seen = 0

    def excite(self, state: dict) -> Optional[str]:
        """Stochastically stimulate an unlearned motor; no body action chosen."""
        if self.rate <= 0 or self.rng.random() >= self.rate:
            return None
        if state.get("is_sleeping", 0.0) >= 50:
            return None

        # Urgent innate actions take priority. Babbling cannot override an
        # obvious threat, food-seeking or involuntary exhaustion.
        for name in ("act_flee", "act_eat", "act_collapse"):
            if state.get(name, 0.0) >= ACTION_THRESHOLDS[name]:
                return None

        # A weak connection is not a usable skill. Do not stop exploring
        # just because a single edge exceeded an arbitrary weight threshold:
        # synaptic input must have enough physical headroom (50 per saturated
        # sensor/drive) to reach the motor's actual firing threshold.
        actionable = {}
        for motor in _EXPLORE_ACTIONS:
            incoming = sum(
                50.0 * max(0.0, float(weight))
                for (src, dst), weight in self.brain.weights.items()
                if dst == motor and (src in CORE_STAT_NEURONS or
                                     src in PURE_INPUT_NEURONS)
            )
            actionable[motor] = incoming >= ACTION_THRESHOLDS[motor]
        actions = [a for a in _EXPLORE_ACTIONS
                   if a in self.brain.positions and not actionable[a]]
        if not actions:
            return None

        neuron = self.rng.choice(actions)
        # Endogenous motor spike, not an action selection. The same neural
        # rank_actions then resolves this against all other action neurons.
        state[neuron] = max(float(state.get(neuron, 0.0)), 96.0)
        self.probes += 1
        return neuron

    def committed(self, episode_id: Optional[str], neuron: Optional[str],
                  behaviour: Optional[str], pre_action_state: dict) -> None:
        """Only executed trial actions get causal credit eligibility."""
        if not episode_id or neuron is None or _BY_BEHAVIOUR.get(behaviour) != neuron:
            return
        self.executed_probes += 1
        if not self.teaching:
            return
        self.pending[episode_id] = (
            neuron, {k: float(v) for k, v in pre_action_state.items()
                     if isinstance(v, (int, float))},
        )

    def process_closed(self) -> int:
        """Turn genuine settled experiences into *recorded* synaptic updates."""
        if not self.teaching:
            return 0
        ledger = self.brain.causal_learning
        changes = 0
        # Process only newly closed outcomes. Rescanning the entire rolling
        # history (up to 400 episodes) every simulation tick made a small
        # experimental feature grow costly with age.
        freshly_closed = max(0, ledger.closed_episodes - self._closed_seen)
        self._closed_seen = ledger.closed_episodes
        new_episodes = list(ledger.history)[-freshly_closed:] if freshly_closed else ()
        for episode in new_episodes:
            trial = self.pending.pop(episode.episode_id, None)
            if trial is None:
                continue
            motor, context = trial
            self.trials_closed += 1

            # Drive value is measured against natural drift without this
            # action. An externally injected feeding cannot appear here,
            # because such an intervention cancels the open episode.
            benefit = 0.0
            for stat, delta in episode.consequence.items():
                importance = VALENCE_WEIGHTS.get(stat)
                if importance:
                    background = ledger.baseline_drift(stat, episode.action)
                    benefit += importance * (delta - background) / 100.0

            cues = []
            for cue, activation in context.items():
                if cue not in self.brain.positions or cue == motor:
                    continue
                if cue in PURE_INPUT_NEURONS:
                    if activation >= 70:
                        cues.append(cue)
                elif cue in CORE_STAT_NEURONS and activation >= 70:
                    cues.append(cue)

            for cue in cues:
                key = (cue, motor)
                record = self.evidence.setdefault(key, _Evidence())
                record.count += 1
                record.total_benefit += benefit
                if record.count < self.trials_to_learn:
                    continue
                if record.mean <= self.minimum_benefit:
                    # Neutral/negative trials do not grow a positive reflex.
                    continue
                # Repeated benefit, not a one-off surprising correlation,
                # progressively builds an ordinary excitatory synapse.
                if self.brain.apply_weight_change(
                    key, delta=self.learning_step * min(1.0, record.mean / 0.10),
                    mechanism="causal_motor_discovery",
                    detail={
                        "note": "repeated beneficial self-initiated motor trials",
                        "mean_baseline_corrected_benefit": round(record.mean, 5),
                        "trials": record.count,
                        "action": episode.action,
                    },
                    episode_id=episode.episode_id,
                    create=True, directed=True,
                ):
                    changes += 1
                    self.connections_taught += 1

        # Scripted feed/clean/set_state events deliberately invalidate
        # currently open causal windows. Their probes must never remain
        # eligible for future unrelated episodes or accumulate indefinitely.
        still_open = {e.episode_id for e in ledger._open}
        for episode_id in tuple(self.pending):
            if episode_id not in still_open:
                self.pending.pop(episode_id)
                self.aborted_trials += 1
        return changes

    def statistics(self):
        return {
            "motor_probes": self.probes,
            "motor_trials_executed": self.executed_probes,
            "motor_trials_closed": self.trials_closed,
            "motor_connections_taught": self.connections_taught,
            "motor_evidence_pairs": len(self.evidence),
            "motor_aborted_trials": self.aborted_trials,
            "motor_pending_trials": len(self.pending),
        }
