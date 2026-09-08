"""
Sleep Replay & Consolidation – core engine (Qt-free)

Biological basis
----------------
While the squid is awake, neurons that fire together accumulate a co-activation
trace – a lightweight, recency-weighted record of "what happened today". This is
the analogue of the hippocampal experience buffer.

When the squid falls asleep, the most strongly co-active experiences are
*replayed*: their connections are strengthened in a series of bursts (the
analogue of sharp-wave ripples during slow-wave sleep). This is systems
consolidation – the day's important co-activations become durable structure.

Sleep also *renormalises* the network. Weak, unused synapses are pruned
(the synaptic-homeostasis / "sleep prunes" hypothesis), so the connectome
reflects what actually mattered instead of only ever accreting.

This module contains only pure logic – no PyQt, no game references – so it can
be unit-tested in isolation. All the side effects (mutating brain weights,
driving animations, touching the UI) live in ``main.py``.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Iterable, Callable, Optional

# A neuron pair is always stored as a sorted tuple so (a, b) == (b, a).
Pair = Tuple[str, str]


def _pair_key(a: str, b: str) -> Pair:
    return (a, b) if a <= b else (b, a)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ReplayConfig:
    """Tunable parameters for accumulation, replay and pruning."""

    # --- Awake: co-activation accumulation -------------------------------
    coactivation_threshold: float = 55.0
    """Both neurons must exceed this activation for a sample to count."""

    trace_decay: float = 0.985
    """Per-sample multiplicative decay of the whole buffer (recency weighting).
    Closer to 1.0 = longer memory of the 'day'. 0.985 ≈ half-life of ~46 samples."""

    memory_bias: float = 0.6
    """How strongly a pair co-occurring in a short-term memory's related_neurons
    is boosted (added per harvest, scaled by memory importance)."""

    max_tracked_pairs: int = 400
    """Hard cap on buffer size; the weakest pairs are dropped when exceeded."""

    # --- Sleep: replay / consolidation -----------------------------------
    replay_top_k: int = 8
    """How many of the strongest experiences are replayed per sleep."""

    replay_cycles: int = 5
    """Number of ripple bursts spread across the sleep episode."""

    replay_strength: float = 0.05
    """Base weight increment applied to a fully-salient pair, per cycle."""

    replay_falloff: float = 0.78
    """Each successive cycle strengthens a little less (ripples fade)."""

    create_missing_connections: bool = True
    """Allow replay to instantiate a connection that co-activated but was
    never wired (Hebbian-style pathway formation during consolidation)."""

    min_experience_samples: int = 4
    """Skip replay entirely until at least this many co-active samples exist."""

    # --- Sleep: pruning / downscaling ------------------------------------
    prune_enabled: bool = True

    prune_threshold: float = 0.06
    """Connections with |weight| below this are candidates for pruning."""

    prune_min_age_sec: float = 240.0
    """Spare connections whose endpoints are younger than this (immature)."""

    synaptic_downscale: float = 0.0
    """Optional multiplicative down-scaling applied to every non-replayed,
    non-immune connection during sleep (0.0 = off). E.g. 0.02 shaves 2%."""


# ---------------------------------------------------------------------------
# Co-activation tracker
# ---------------------------------------------------------------------------

class CoactivationTracker:
    """Recency-weighted record of which neuron pairs fire together."""

    def __init__(self, config: ReplayConfig):
        self.config = config
        self._scores: Dict[Pair, float] = defaultdict(float)
        self.sample_count: int = 0
        self.total_samples_ever: int = 0

    # -- accumulation ------------------------------------------------------

    def record_sample(self, active: Dict[str, float]) -> int:
        """
        Record one snapshot of neuron activations.

        ``active`` maps neuron name -> activation (0-100) and should already be
        filtered to learnable neurons (no pure inputs / excluded / connectors).

        Returns the number of co-active pairs seen in this sample.
        """
        cfg = self.config

        # Decay the whole buffer first so older experiences fade ("today").
        if self._scores:
            decay = cfg.trace_decay
            for k in list(self._scores.keys()):
                self._scores[k] *= decay

        # Neurons that crossed the co-activation threshold this tick.
        firing = [(n, v) for n, v in active.items()
                  if isinstance(v, (int, float)) and v >= cfg.coactivation_threshold]

        pairs_seen = 0
        for i in range(len(firing)):
            n1, v1 = firing[i]
            for j in range(i + 1, len(firing)):
                n2, v2 = firing[j]
                # Contribution = joint activation strength (the weaker of the two,
                # normalised) – both must be strongly on to count for much.
                contribution = min(v1, v2) / 100.0
                self._scores[_pair_key(n1, n2)] += contribution
                pairs_seen += 1

        self.sample_count += 1
        self.total_samples_ever += 1

        self._enforce_cap()
        return pairs_seen

    def bias_from_memory(self, related_neurons: Iterable[str], importance: float = 1.0) -> None:
        """
        Boost every pair drawn from a memory's ``related_neurons`` list, so
        experiences the squid actually remembered get preferentially replayed.
        """
        neurons = [n for n in related_neurons if n]
        if len(neurons) < 2:
            return
        bump = self.config.memory_bias * max(0.2, min(3.0, importance))
        for i in range(len(neurons)):
            for j in range(i + 1, len(neurons)):
                self._scores[_pair_key(neurons[i], neurons[j])] += bump

    def _enforce_cap(self) -> None:
        cap = self.config.max_tracked_pairs
        if len(self._scores) <= cap:
            return
        # Keep the strongest ``cap`` pairs, drop the rest.
        ranked = sorted(self._scores.items(), key=lambda kv: kv[1], reverse=True)
        self._scores = defaultdict(float, dict(ranked[:cap]))

    # -- queries -----------------------------------------------------------

    def top_pairs(self, k: int) -> List[Tuple[Pair, float]]:
        """Return up to ``k`` strongest (pair, score), highest first."""
        if not self._scores:
            return []
        ranked = sorted(self._scores.items(), key=lambda kv: kv[1], reverse=True)
        # Drop negligible traces so we never replay noise.
        ranked = [(p, s) for p, s in ranked if s > 1e-4]
        return ranked[:k]

    def buffer_size(self) -> int:
        return len(self._scores)

    def peak_score(self) -> float:
        return max(self._scores.values(), default=0.0)

    def clear(self) -> None:
        self._scores.clear()
        self.sample_count = 0

    def decay_day(self, factor: float = 0.5) -> None:
        """Called after a sleep: fade the buffer so a new 'day' begins fresh
        while retaining a little momentum from yesterday."""
        if factor <= 0:
            self.clear()
            return
        for k in list(self._scores.keys()):
            self._scores[k] *= factor
            if self._scores[k] < 1e-4:
                del self._scores[k]
        self.sample_count = 0


# ---------------------------------------------------------------------------
# Replay plan
# ---------------------------------------------------------------------------

@dataclass
class ReplayItem:
    """A single connection to strengthen during one replay cycle."""
    pair: Pair
    delta: float
    salience: float  # normalised 0-1, for logging / colouring


@dataclass
class ReplaySession:
    """The full plan produced when the squid falls asleep."""
    cycles: List[List[ReplayItem]] = field(default_factory=list)
    selected: List[Tuple[Pair, float]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    _cursor: int = 0

    @property
    def total_cycles(self) -> int:
        return len(self.cycles)

    @property
    def finished(self) -> bool:
        return self._cursor >= len(self.cycles)

    def next_cycle(self) -> Optional[List[ReplayItem]]:
        if self.finished:
            return None
        batch = self.cycles[self._cursor]
        self._cursor += 1
        return batch

    @property
    def cycles_done(self) -> int:
        return self._cursor


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class ReplayStats:
    days_completed: int = 0
    total_replayed: int = 0
    total_pruned: int = 0
    last_replay_pairs: int = 0
    last_pruned: int = 0
    last_cycles: int = 0
    last_sleep_time: float = 0.0


class SleepReplayEngine:
    """
    Ties the co-activation tracker to a replay/prune plan. Pure logic:
    the caller feeds it samples, asks it to build a plan on sleep onset,
    applies the returned deltas to real weights, then asks what to prune.
    """

    def __init__(self, config: Optional[ReplayConfig] = None):
        self.config = config or ReplayConfig()
        self.tracker = CoactivationTracker(self.config)
        self.stats = ReplayStats()
        self._replayed_this_sleep: set[Pair] = set()

    # -- awake -------------------------------------------------------------

    def record_sample(self, active: Dict[str, float]) -> int:
        return self.tracker.record_sample(active)

    def harvest_memory(self, memories: Iterable[dict]) -> int:
        """
        Pull ``related_neurons`` out of short-term memory dicts and bias the
        buffer toward them. Returns how many memories contributed.
        Defensive: tolerates arbitrary / missing fields.
        """
        used = 0
        for mem in memories or []:
            try:
                related = mem.get('related_neurons') or []
                if len(related) >= 2:
                    self.tracker.bias_from_memory(related, mem.get('importance', 1.0))
                    used += 1
            except Exception:
                continue
        return used

    # -- sleep onset -------------------------------------------------------

    def has_enough_to_replay(self) -> bool:
        return (self.tracker.sample_count >= self.config.min_experience_samples
                and self.tracker.buffer_size() >= 1)

    def build_session(self) -> ReplaySession:
        """
        Select the day's strongest experiences and lay out the replay bursts.
        Returns an (possibly empty) ReplaySession.
        """
        cfg = self.config
        session = ReplaySession()
        self._replayed_this_sleep = set()

        selected = self.tracker.top_pairs(cfg.replay_top_k)
        if not selected:
            return session

        session.selected = selected
        peak = max((s for _, s in selected), default=1.0) or 1.0

        for c in range(cfg.replay_cycles):
            cycle_scale = cfg.replay_strength * (cfg.replay_falloff ** c)
            batch: List[ReplayItem] = []
            for pair, score in selected:
                salience = max(0.0, min(1.0, score / peak))
                delta = cycle_scale * salience
                if delta <= 1e-5:
                    continue
                batch.append(ReplayItem(pair=pair, delta=delta, salience=salience))
                self._replayed_this_sleep.add(pair)
            if batch:
                session.cycles.append(batch)

        return session

    # -- pruning -----------------------------------------------------------

    def plan_prune(
        self,
        weights: Dict[Pair, float],
        is_immune: Callable[[str, str], bool],
    ) -> List[Pair]:
        """
        Decide which connections to remove. ``is_immune(n1, n2)`` should return
        True for connections that must be spared (connectors, immature neurons).
        Connections replayed during *this* sleep are always spared.
        """
        if not self.config.prune_enabled:
            return []

        threshold = self.config.prune_threshold
        to_prune: List[Pair] = []

        for pair, weight in list(weights.items()):
            if not (isinstance(pair, tuple) and len(pair) == 2):
                continue
            n1, n2 = pair
            key = _pair_key(n1, n2)
            if key in self._replayed_this_sleep:
                continue
            if abs(weight) >= threshold:
                continue
            try:
                if is_immune(n1, n2):
                    continue
            except Exception:
                # If immunity can't be determined, err on the side of keeping.
                continue
            to_prune.append(pair)

        return to_prune

    def plan_downscale(
        self,
        weights: Dict[Pair, float],
        is_immune: Callable[[str, str], bool],
    ) -> Dict[Pair, float]:
        """
        Optional synaptic homeostasis: return new (reduced) weights for every
        non-replayed, non-immune connection. Empty dict when disabled.
        """
        factor = self.config.synaptic_downscale
        if factor <= 0.0:
            return {}
        keep = 1.0 - factor
        updates: Dict[Pair, float] = {}
        for pair, weight in list(weights.items()):
            if not (isinstance(pair, tuple) and len(pair) == 2):
                continue
            n1, n2 = pair
            if _pair_key(n1, n2) in self._replayed_this_sleep:
                continue
            try:
                if is_immune(n1, n2):
                    continue
            except Exception:
                continue
            updates[pair] = weight * keep
        return updates

    # -- bookkeeping -------------------------------------------------------

    def finish_day(self, replayed: int, pruned: int, cycles: int) -> None:
        self.stats.days_completed += 1
        self.stats.total_replayed += replayed
        self.stats.total_pruned += pruned
        self.stats.last_replay_pairs = replayed
        self.stats.last_pruned = pruned
        self.stats.last_cycles = cycles
        self.stats.last_sleep_time = time.time()
        self.tracker.decay_day(0.5)

    def get_stats(self) -> dict:
        return {
            'days_completed': self.stats.days_completed,
            'total_replayed': self.stats.total_replayed,
            'total_pruned': self.stats.total_pruned,
            'last_replay_pairs': self.stats.last_replay_pairs,
            'last_pruned': self.stats.last_pruned,
            'last_cycles': self.stats.last_cycles,
            'buffer_size': self.tracker.buffer_size(),
            'samples_today': self.tracker.sample_count,
            'peak_score': round(self.tracker.peak_score(), 3),
        }
