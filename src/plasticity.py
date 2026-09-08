"""
plasticity.py - the project's single synaptic plasticity implementation.

Dosidicus learns on two timescales that a snapshot-based rule cannot bridge:

  * homeostatic drives (hunger, happiness, anxiety ...) drift slowly, taking
    30-60 seconds to move 10 points;
  * event neurons (can_see_food, is_eating, is_startled ...) flip in a single
    tick and are ON for roughly 2% of the time.

The previous rule sampled the network once every 30 seconds and multiplied the
two activations it happened to see. Measured over 300 ticks, that sampler
caught 0 of the 7 ticks where can_see_food was ON, so the neurons carrying
what actually happened to the squid were structurally excluded from learning.
It also used delta = lr * a1 * a2, which is never negative, so no amount of
experience could ever produce an inhibitory synapse - and an avoidance
behaviour ("why is yours afraid of poop?") IS an inhibitory synapse.

This module fixes both:

  1. ELIGIBILITY TRACE. Co-activation is accumulated every tick and committed
     on the slow learning cycle, so a one-second food sighting contributes in
     proportion to the window instead of being invisible. The interval becomes
     a pacing choice rather than a correctness one.

  2. CORRELATION RULE. delta = lr * r(a1, a2) over the window, where r is the
     Pearson correlation against each neuron's OWN mean rather than a fixed
     midpoint. Pairs that vary together strengthen, pairs that vary oppositely
     go NEGATIVE, and unrelated pairs decay to zero instead of saturating at
     +1. A neuron held at a constant has no variance and so teaches nothing,
     which is correct: you cannot learn from an invariant. With
     learning_rate == weight_decay a synapse converges to exactly the
     correlation between its endpoints, which makes every weight in the
     network readable as a statement about the squid's experience.

  3. STDP IS CORE. Spike-timing contributions are blended in here rather than
     by a plugin monkey-patching the worker.

Sensors may be learning SOURCES but never TARGETS: the world writes them, so a
synapse pointing into one could never do anything. Excluding them entirely -
as the old code did - is what stopped the squid learning about its
environment at all.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .brain_constants import NON_PROPAGATED_NEURONS, is_learning_target

Pair = Tuple[str, str]

# The neutral baseline. Identical to the one propagate_activations() centres on.
BASELINE = 50.0


@dataclass
class PlasticityConfig:
    """Tuning for the plasticity engine.

    Defaults were chosen by simulating a meaningful pair (covariance 0.16)
    against the noise floor over 30 simulated minutes, with the real pair
    rotation in place. The old settings separated signal from noise by +0.020
    (i.e. not at all); these separate it by roughly +0.30.
    """

    # Hebbian. Setting learning_rate == weight_decay makes the equilibrium
    # weight equal the correlation between the two neurons: a perfectly
    # reliable association converges to 1.0, a perfectly inverse one to -1.0,
    # and an unrelated pair decays to 0. tau = 1/decay = 25 commits, so at a
    # 20s cadence a synapse settles over roughly 8 minutes of play.
    learning_rate: float = 0.04
    weight_decay: float = 0.04
    learning_interval_ms: int = 20000    # commit cadence (pacing, not correctness)
    min_weight: float = -1.0
    max_weight: float = 1.0

    # Below this variance a neuron is treated as constant and teaches nothing.
    min_variance: float = 0.0004         # sd of 2 activation points out of 100

    # How many pairs to commit per cycle. A fixed 2 meant a given synapse in a
    # 20-neuron brain only updated every 47 minutes - the more the brain grew
    # through neurogenesis, the less each synapse learned.
    min_pairs_per_cycle: int = 4
    pairs_fraction: float = 0.5          # ...or half the candidate pool, whichever is larger
    max_pairs_per_cycle: int = 64

    # New neurons learn faster while they bed in.
    new_neuron_lr_multiplier: float = 2.0

    # STDP blend. 0.0 = pure Hebbian, 1.0 = pure spike timing.
    stdp_weight: float = 0.4
    stdp_enabled: bool = True

    # A trace entry this small is treated as no evidence at all.
    trace_epsilon: float = 1e-6

    @classmethod
    def from_learning_config(cls, config) -> "PlasticityConfig":
        """Build from the game's LearningConfig, honouring config.ini."""
        cfg = cls()
        hebb = getattr(config, 'hebbian', None) or {}
        cfg.learning_rate = float(hebb.get('base_learning_rate', cfg.learning_rate))
        cfg.weight_decay = float(hebb.get('weight_decay', cfg.weight_decay))
        cfg.learning_interval_ms = int(hebb.get('learning_interval', cfg.learning_interval_ms))
        cfg.min_weight = float(hebb.get('min_weight', cfg.min_weight))
        cfg.max_weight = float(hebb.get('max_weight', cfg.max_weight))
        if 'max_hebbian_pairs' in hebb:
            cfg.min_pairs_per_cycle = max(1, int(hebb['max_hebbian_pairs']))
        if 'stdp_weight' in hebb:
            cfg.stdp_weight = float(hebb['stdp_weight'])
        return cfg


class PlasticityEngine:
    """Accumulates co-activation every tick; commits weight changes on a cycle."""

    def __init__(self, config: Optional[PlasticityConfig] = None, stdp_learner=None):
        self.config = config or PlasticityConfig()

        # Running statistics for a TRUE covariance over the window:
        #   cov(x,y) = E[xy] - E[x]E[y]
        # Centring on a fixed midpoint instead would make a mostly-OFF event
        # neuron read as permanently "below neutral", so its associations would
        # encode base rates rather than contingency - can_see_food would come
        # out anti-correlated with happiness simply because food is rare.
        self._sum_xy: Dict[Pair, float] = defaultdict(float)
        self._sum_x: Dict[str, float] = defaultdict(float)
        self._sum_x2: Dict[str, float] = defaultdict(float)
        self._count_x: Dict[str, int] = defaultdict(int)
        self._opportunities: Dict[Pair, int] = defaultdict(int)
        self.samples_since_commit: int = 0

        self.stdp = stdp_learner
        if self.stdp is None and self.config.stdp_enabled:
            try:
                from .stdp import STDPLearner
                self.stdp = STDPLearner()
            except Exception:
                self.stdp = None

        # Rotation bookkeeping, so every pair gets its turn.
        self._last_committed: List[Pair] = []
        self._commit_count: int = 0
        self.total_updates: int = 0
        self.last_commit_time: float = time.time()

    # ------------------------------------------------------------------
    # Per-tick observation
    # ------------------------------------------------------------------
    @staticmethod
    def _activation(raw) -> Optional[float]:
        if isinstance(raw, bool):
            return 100.0 if raw else 0.0
        if isinstance(raw, (int, float)):
            return float(raw)
        return None

    def observe(self, state: Dict[str, float], candidates: Optional[Sequence[str]] = None,
                timestamp: Optional[float] = None) -> int:
        """Accumulate one tick of evidence. Cheap: O(pairs).

        Call every simulation tick. This is what lets a 1-second event survive
        until the next commit.
        """
        if candidates is None:
            candidates = [n for n in state.keys()]

        values: Dict[str, float] = {}
        for name in candidates:
            v = self._activation(state.get(name))
            if v is not None:
                values[name] = v

        names = sorted(values)
        for name in names:
            x = values[name] / 100.0
            self._sum_x[name] += x
            self._sum_x2[name] += x * x
            self._count_x[name] += 1

        for i, n1 in enumerate(names):
            x1 = values[n1] / 100.0
            for n2 in names[i + 1:]:
                key = (n1, n2)
                self._sum_xy[key] += x1 * (values[n2] / 100.0)
                self._opportunities[key] += 1

        self.samples_since_commit += 1

        if self.stdp is not None and self.config.stdp_enabled:
            try:
                self.stdp.record_state(values, timestamp)
                # Mark what was carrying signal this tick, so a consequence
                # arriving seconds later can reach back to it. Laying these on
                # the commit cycle instead put them out of reach of every
                # outcome the squid ever had.
                self.stdp.lay_eligibility_traces(values, timestamp)
            except Exception:
                pass  # spike tracking must never break the simulation tick

        return len(names)

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------
    def eligible_neurons(self, neuron_names: Iterable[str],
                         excluded: Iterable[str] = (),
                         connectors: Iterable[str] = ()) -> List[str]:
        """Neurons that may take part in learning.

        Sensors are included: they are legitimate learning SOURCES, and
        excluding them is what stopped the squid associating what it saw with
        what happened next. Orientation is handled at commit time so no
        synapse ever points INTO a sensor.
        """
        excluded = set(excluded or ())
        connectors = set(connectors or ())
        return [n for n in neuron_names if n not in excluded and n not in connectors]

    def pairs_per_cycle(self, candidate_pairs: int) -> int:
        cfg = self.config
        want = max(cfg.min_pairs_per_cycle, int(candidate_pairs * cfg.pairs_fraction))
        return max(1, min(cfg.max_pairs_per_cycle, want, candidate_pairs))

    @staticmethod
    def orient(pair: Pair, weights: Dict[Pair, float]) -> Optional[Pair]:
        """Choose the direction for this synapse.

        An existing edge keeps its direction. A new edge points at whichever
        end a synapse could actually influence - a network-driven neuron via
        propagation, or a core stat via modulation. If neither end qualifies
        (two sensors) the pair is skipped rather than silently creating a
        weight that nothing can ever read.
        """
        n1, n2 = pair
        if (n1, n2) in weights:
            return (n1, n2)
        if (n2, n1) in weights:
            return (n2, n1)
        if is_learning_target(n2):
            return (n1, n2)
        if is_learning_target(n1):
            return (n2, n1)
        return None

    def commit(self, weights: Dict[Pair, float], neuron_names: Iterable[str],
               excluded: Iterable[str] = (), connectors: Iterable[str] = (),
               new_neurons: Iterable[str] = ()) -> Dict:
        """Turn accumulated evidence into weight changes.

        Returns a payload shaped like the one BrainWidget._on_hebbian_complete
        already consumes, so the Learning tab and the network view keep working.
        """
        cfg = self.config
        new_neurons = set(new_neurons or ())
        candidates = set(self.eligible_neurons(neuron_names, excluded, connectors))

        # Rank pairs by the strength of the evidence, not by a snapshot.
        scored: List[Tuple[float, Pair, float]] = []
        for pair, sum_xy in self._sum_xy.items():
            if pair[0] not in candidates or pair[1] not in candidates:
                continue
            opportunities = self._opportunities.get(pair, 0)
            if opportunities <= 0:
                continue
            mean_cov = self._correlation(pair, sum_xy, opportunities)
            if abs(mean_cov) < cfg.trace_epsilon:
                continue
            score = abs(mean_cov)
            if pair in self._last_committed:
                score *= 0.25   # rotate, but do not exile strong evidence
            scored.append((score, pair, mean_cov))

        scored.sort(key=lambda item: item[0], reverse=True)
        take = self.pairs_per_cycle(len(scored)) if scored else 0
        chosen = scored[:take]

        weight_updates: Dict[Pair, Dict] = {}
        updated_pairs: List[Pair] = []

        for _, pair, mean_cov in chosen:
            edge = self.orient(pair, weights)
            if edge is None:
                continue

            old_w = float(weights.get(edge, 0.0))
            is_new = edge not in weights

            lr = cfg.learning_rate
            if pair[0] in new_neurons or pair[1] in new_neurons:
                lr *= cfg.new_neuron_lr_multiplier

            hebb_delta = lr * mean_cov

            # The DIRECTED delta for the synapse actually being updated.
            #
            # This used to ask compute_symmetric_stdp(), which returns the
            # stronger of the two orderings - and since the causal ordering
            # always beats the acausal one, it was essentially always positive.
            # Worse, that value was applied to whichever direction orient()
            # had chosen, which need not be the direction STDP measured. So
            # LTD never reached a weight, and LTP could be applied backwards:
            # a synapse whose own ordering was acausal got strengthened.
            #
            # Asking about edge[0] -> edge[1] gives potentiation when this
            # synapse's own presynaptic neuron leads, and depression when it
            # lags, which is what spike-timing plasticity means.
            stdp_delta = 0.0
            stdp_direction = 'none'
            if self.stdp is not None and cfg.stdp_enabled and cfg.stdp_weight > 0:
                try:
                    stdp_delta = float(
                        self.stdp.compute_stdp_delta(edge[0], edge[1]) or 0.0)
                except Exception:
                    stdp_delta = 0.0
                if stdp_delta > 0:
                    stdp_direction = 'causal'
                elif stdp_delta < 0:
                    stdp_direction = 'acausal'


            # Blend ONLY where STDP actually has an opinion. Spike timing is
            # silent for most pairs on most cycles, and blending its zero in
            # regardless would drag every estimate toward the middle - which
            # would also break the property that a synapse converges to the
            # correlation between its endpoints.
            if stdp_delta != 0.0:
                blend = cfg.stdp_weight
                delta = (1.0 - blend) * hebb_delta + blend * stdp_delta * lr
            else:
                delta = hebb_delta

            new_w = old_w + delta - (old_w * cfg.weight_decay)
            new_w = max(cfg.min_weight, min(cfg.max_weight, new_w))

            weight_updates[edge] = {
                'old_weight': old_w,
                'new_weight': new_w,
                'is_new_connection': is_new,
                'mean_covariance': mean_cov,
                'hebbian_delta': hebb_delta,
                'stdp_delta': stdp_delta,
                'stdp_direction': stdp_direction,
                'is_ltp': stdp_delta > 0,
                'is_ltd': stdp_delta < 0,
                'stdp_weight': cfg.stdp_weight if stdp_delta else 0.0,
                'samples': self._opportunities.get(pair, 0),
            }
            updated_pairs.append(edge)

        self._last_committed = [p for _, p, _ in chosen]
        self._commit_count += 1
        self.total_updates += len(updated_pairs)
        self.last_commit_time = time.time()

        window_samples = self.samples_since_commit
        self.reset()

        return {
            'updated_pairs': updated_pairs,
            'weight_updates': weight_updates,
            'window_samples': window_samples,
            'candidate_pairs': len(scored),
        }

    def reset(self) -> None:
        """Discard all accumulated evidence and rotation history."""
        self._sum_xy.clear()
        self._sum_x.clear()
        self._sum_x2.clear()
        self._count_x.clear()
        self._opportunities.clear()
        self.samples_since_commit = 0
        self._last_committed = []

    def _correlation(self, pair: Pair, sum_xy: float, n: int) -> float:
        """Pearson correlation between the pair over the window, in [-1, 1].

        Correlation rather than raw covariance because it is scale-free: a
        synapse should encode how RELIABLY two neurons move together, not how
        large their swings happen to be. can_see_food swings 0-100 while
        satisfaction may only breathe by 15, and both associations deserve to
        be learnable. It also makes the rule interpretable - with
        learning_rate == weight_decay, a synapse converges to exactly the
        correlation between its endpoints.
        """
        n1, n2 = pair
        c1 = self._count_x.get(n1, 0)
        c2 = self._count_x.get(n2, 0)
        if c1 < 2 or c2 < 2 or n < 2:
            return 0.0

        mean_x = self._sum_x[n1] / c1
        mean_y = self._sum_x[n2] / c2
        var_x = max(0.0, self._sum_x2[n1] / c1 - mean_x * mean_x)
        var_y = max(0.0, self._sum_x2[n2] / c2 - mean_y * mean_y)

        # A neuron that barely moves carries no information; treating its
        # rounding noise as signal would manufacture associations from nothing.
        if var_x < self.config.min_variance or var_y < self.config.min_variance:
            return 0.0

        cov = (sum_xy / n) - (mean_x * mean_y)
        r = cov / math.sqrt(var_x * var_y)
        return max(-1.0, min(1.0, r))

    # ------------------------------------------------------------------
    # Introspection / persistence
    # ------------------------------------------------------------------
    def trace_snapshot(self, top: int = 10) -> List[Tuple[Pair, float]]:
        """Strongest evidence accumulated so far - for the Learning tab."""
        rows = []
        for pair, sum_xy in self._sum_xy.items():
            n = self._opportunities.get(pair, 0)
            if n:
                rows.append((pair, self._correlation(pair, sum_xy, n)))
        rows.sort(key=lambda r: abs(r[1]), reverse=True)
        return rows[:top]

    def get_stats(self) -> Dict:
        stats = {
            'samples_since_commit': self.samples_since_commit,
            'tracked_pairs': len(self._sum_xy),
            'commits': self._commit_count,
            'total_updates': self.total_updates,
            'learning_rate': self.config.learning_rate,
            'weight_decay': self.config.weight_decay,
            'stdp_weight': self.config.stdp_weight if self.stdp else 0.0,
        }
        if self.stdp is not None:
            try:
                stats['stdp'] = self.stdp.get_stats()
            except Exception:
                pass
        return stats

    def to_dict(self) -> Dict:
        data = {
            'commit_count': self._commit_count,
            'total_updates': self.total_updates,
            'config': {
                'learning_rate': self.config.learning_rate,
                'weight_decay': self.config.weight_decay,
                'learning_interval_ms': self.config.learning_interval_ms,
                'stdp_weight': self.config.stdp_weight,
            },
        }
        if self.stdp is not None:
            try:
                data['stdp'] = self.stdp.to_dict()
            except Exception:
                pass
        return data

    def from_dict(self, data: Dict) -> None:
        if not isinstance(data, dict):
            return
        self._commit_count = int(data.get('commit_count', 0))
        self.total_updates = int(data.get('total_updates', 0))
        cfg = data.get('config') or {}
        self.config.learning_rate = float(cfg.get('learning_rate', self.config.learning_rate))
        self.config.weight_decay = float(cfg.get('weight_decay', self.config.weight_decay))
        self.config.learning_interval_ms = int(
            cfg.get('learning_interval_ms', self.config.learning_interval_ms))
        self.config.stdp_weight = float(cfg.get('stdp_weight', self.config.stdp_weight))
        if self.stdp is not None and 'stdp' in data:
            try:
                self.stdp.from_dict(data['stdp'])
            except Exception:
                pass
