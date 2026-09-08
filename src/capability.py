"""
capability.py - what this brain cannot currently do.

Neurogenesis used to be event-driven: something happened (anxiety crossed 75,
curiosity crossed 70, a reward counter ticked over) and therefore a neuron
appeared. That is growth as a reflex. It says nothing about whether the
network needed the neuron, and a squid living a busy life grew structure it
had no use for while a squid with a real, persistent problem grew none.

This module replaces the trigger with a question the network asks about
itself:

    Is there something I cannot usefully represent, respond to, or express?

A deficit is only actionable when it is *persistent* and *unresolved*: the
ordinary machinery - synaptic plasticity, sleep consolidation, causal learning -
has had its chance across several evaluations and the problem is still there.
Only then does the organism spend structure on it.

Five kinds of deficit, each measured from the live network rather than from
an event:

  representation   A situation keeps recurring and no existing neuron's
                   activation distinguishes it from any other situation. The
                   brain literally cannot tell it apart, so it cannot learn
                   anything specific to it.

  regulation       A drive sits outside its comfortable range for a long time
                   while the synapses that would pull it back are absent,
                   saturated, or too weak. The network cannot respond.

  expression       Causal learning has established that a cue and an action
                   produce an outcome, but there is no synaptic pathway from
                   the cue to that outcome. The brain knows something it has
                   no structure to act on.

  differentiation  One neuron is driven by two sources that are strongly
                   anti-correlated: it is being asked to stand for two
                   incompatible situations at once, so it represents neither.

  connectivity     Part of the network has been left unreachable.

Everything here is diagnosis. Growing the remedy is neurogenesis.py's job.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

from .brain_constants import (CORE_STAT_NEURONS, PURE_INPUT_NEURONS,
                              is_learning_target, is_network_driven)

DEFICIT_KINDS = ('representation', 'regulation', 'expression',
                 'differentiation', 'connectivity')

# The range each drive is comfortable in. Outside it, the squid is in trouble
# and the network is supposed to be doing something about it.
COMFORT_BANDS: Dict[str, Tuple[float, float]] = {
    'hunger': (0.0, 65.0),
    'anxiety': (0.0, 60.0),
    'sleepiness': (0.0, 85.0),
    'cleanliness': (35.0, 100.0),
    'happiness': (30.0, 100.0),
    'satisfaction': (25.0, 100.0),
    'curiosity': (15.0, 95.0),
}

# A synapse this close to the clamp has nothing left to give.
SATURATION = 0.85

# Only used to WORD the diagnosis, never to decide it: a push below this is
# described as too weak, above it as present but ineffective. One synapse at
# weight w with its source fully on contributes w/2, so 0.25 is roughly one
# solid, half-strength connection actively correcting.
MIN_CORRECTIVE_PUSH = 0.25

_MAX_SIGNATURES = 24
_CORRELATION_HALFLIFE = 600.0     # seconds; long-run, so it survives a commit
_MIN_TICKS_FOR_STATS = 40


def regulation_specialisation(stat: str, too_high: bool) -> str:
    """Which existing specialisation remedies this drive going the wrong way.

    Keeps the specialisation vocabulary the rest of the project already knows
    (appearance, colours, caps, the Laboratory) attached to the new,
    capability-based reasons for growth.
    """
    table = {
        ('anxiety', True): 'anxiety_regulation',
        ('hunger', True): 'hunger_stress_response',
        ('cleanliness', False): 'filth_avoidance',
        ('sleepiness', True): 'rest_reward',
        ('happiness', False): 'general_reward',
        ('satisfaction', False): 'general_reward',
        ('curiosity', False): 'general_novelty_processing',
    }
    return table.get((stat, too_high),
                     'general_stress_coping' if too_high else 'general_reward')


def _band_word(value: float) -> str:
    if value < 35.0:
        return 'low'
    if value > 65.0:
        return 'high'
    return 'mid'


class _Running:
    """Streaming mean/variance for one neuron."""

    __slots__ = ('n', 'total', 'total_sq')

    def __init__(self):
        self.n = 0
        self.total = 0.0
        self.total_sq = 0.0

    def add(self, value: float) -> None:
        self.n += 1
        self.total += value
        self.total_sq += value * value

    @property
    def mean(self) -> float:
        return self.total / self.n if self.n else 0.0

    @property
    def var(self) -> float:
        if self.n < 2:
            return 0.0
        return max(0.0, self.total_sq / self.n - self.mean ** 2)

    def to_dict(self) -> dict:
        return {'n': self.n, 'total': self.total, 'total_sq': self.total_sq}

    @classmethod
    def from_dict(cls, d: dict) -> '_Running':
        r = cls()
        r.n = int(d.get('n', 0))
        r.total = float(d.get('total', 0.0))
        r.total_sq = float(d.get('total_sq', 0.0))
        return r


@dataclass
class Deficit:
    """Something the network cannot currently do, and what would fix it."""
    kind: str
    key: str
    summary: str
    target: str = ""
    sources: List[str] = field(default_factory=list)
    remedy: str = ""
    severity: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_type: str = 'novelty'
    specialization: str = 'undefined'

    # Persistence bookkeeping, filled in by the monitor.
    first_seen: float = 0.0
    last_seen: float = 0.0
    observations: int = 0
    initial_severity: float = 0.0

    @property
    def age(self) -> float:
        return max(0.0, self.last_seen - self.first_seen)

    @property
    def unresolved(self) -> bool:
        """True when ordinary learning has not been reducing it.

        A deficit that is shrinking on its own does not need new structure -
        the network is already handling it, just slowly.
        """
        if self.initial_severity <= 0:
            return True
        return self.severity >= self.initial_severity * 0.8

    def to_dict(self) -> dict:
        return {
            'kind': self.kind, 'key': self.key, 'summary': self.summary,
            'target': self.target, 'sources': list(self.sources),
            'remedy': self.remedy, 'severity': self.severity,
            'evidence': self.evidence, 'suggested_type': self.suggested_type,
            'specialization': self.specialization,
            'first_seen': self.first_seen, 'last_seen': self.last_seen,
            'observations': self.observations,
            'initial_severity': self.initial_severity,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Deficit':
        return cls(
            kind=str(d.get('kind', 'representation')),
            key=str(d.get('key', '')),
            summary=str(d.get('summary', '')),
            target=str(d.get('target', '')),
            sources=list(d.get('sources') or []),
            remedy=str(d.get('remedy', '')),
            severity=float(d.get('severity', 0.0)),
            evidence=dict(d.get('evidence') or {}),
            suggested_type=str(d.get('suggested_type', 'novelty')),
            specialization=str(d.get('specialization', 'undefined')),
            first_seen=float(d.get('first_seen', 0.0)),
            last_seen=float(d.get('last_seen', 0.0)),
            observations=int(d.get('observations', 0)),
            initial_severity=float(d.get('initial_severity', 0.0)),
        )


@dataclass
class CapabilityConfig:
    min_observations: int = 3        # evaluations a deficit must survive
    min_age: float = 20.0            # ...and seconds it must persist
    min_severity: float = 0.35
    # representation
    signature_recurrence: int = 6
    discriminability_floor: float = 0.55
    # regulation
    out_of_band_fraction: float = 0.55
    regulation_window: int = 240     # ticks
    # differentiation
    conflict_correlation: float = -0.4
    conflict_weight: float = 0.25


class CapabilityMonitor:
    """Diagnoses what the network cannot do. Owned by the brain."""

    def __init__(self, brain=None, config: Optional[CapabilityConfig] = None):
        self.brain = brain
        self.config = config or CapabilityConfig()

        self.ticks = 0
        self._global: Dict[str, _Running] = {}
        self._signatures: Dict[str, Dict[str, Any]] = {}

        # Long-run co-activation, kept independently of the plasticity engine
        # because that one is reset on every commit and a structural question
        # needs a longer memory than a learning cycle.
        self._co: Dict[Tuple[str, str], float] = {}
        self._mean: Dict[str, float] = {}
        self._var: Dict[str, float] = {}
        self._decay_last = time.time()

        # Drive comfort tracking.
        self._band_history: Dict[str, Deque[bool]] = {}

        self.active: Dict[str, Deficit] = {}
        self.resolved: Deque[Tuple[float, str, str]] = deque(maxlen=40)
        self.evaluations = 0
        self.last_evaluation: List[Deficit] = []

    # ==================================================================
    # Per-tick observation
    # ==================================================================
    def observe(self, state: Dict[str, Any]) -> None:
        """Accumulate the evidence every diagnosis is built from. O(neurons²)
        but only every fourth tick, on a brain of a few dozen neurons."""
        values: Dict[str, float] = {}
        for name, raw in (state or {}).items():
            if isinstance(raw, bool):
                values[name] = 100.0 if raw else 0.0
            elif isinstance(raw, (int, float)):
                values[name] = float(raw)
        if not values:
            return

        self.ticks += 1

        for name, value in values.items():
            entry = self._global.get(name)
            if entry is None:
                entry = _Running()
                self._global[name] = entry
            entry.add(value)

        signature = self.situation_signature(values)
        if signature:
            self._record_signature(signature, values)

        for stat, (low, high) in COMFORT_BANDS.items():
            value = values.get(stat)
            if value is None:
                continue
            history = self._band_history.get(stat)
            if history is None:
                history = deque(maxlen=self.config.regulation_window)
                self._band_history[stat] = history
            history.append(not (low <= value <= high))

        if self.ticks % 4 == 0:
            self._update_correlations(values)

    # ------------------------------------------------------------------
    def situation_signature(self, values: Dict[str, float]) -> str:
        """A compact, stable name for 'the kind of situation the squid is in'.

        Built from what the squid can actually perceive plus the shape of its
        drives, because that is the input the network would have to work from
        if it were to represent the situation at all.
        """
        parts: List[str] = []
        for name in sorted(values):
            if name not in PURE_INPUT_NEURONS:
                continue
            value = values[name]
            if value >= 70.0:
                parts.append(name)
            elif value <= 5.0:
                continue
        drives = [(n, values[n]) for n in sorted(CORE_STAT_NEURONS) if n in values]
        drives.sort(key=lambda kv: -abs(kv[1] - 50.0))
        for name, value in drives[:2]:
            if abs(value - 50.0) >= 18.0:
                parts.append(f"{name}-{_band_word(value)}")
        if not parts:
            return ""
        return "|".join(parts[:4])

    def _record_signature(self, signature: str, values: Dict[str, float]) -> None:
        entry = self._signatures.get(signature)
        if entry is None:
            if len(self._signatures) >= _MAX_SIGNATURES:
                stalest = min(self._signatures.items(),
                              key=lambda kv: kv[1]['last_seen'])[0]
                del self._signatures[stalest]
            entry = {'count': 0, 'stats': {}, 'first_seen': time.time(),
                     'last_seen': time.time(),
                     'defining': [p.split('-')[0] for p in signature.split('|')]}
            self._signatures[signature] = entry
        entry['count'] += 1
        entry['last_seen'] = time.time()
        stats: Dict[str, _Running] = entry['stats']
        for name, value in values.items():
            run = stats.get(name)
            if run is None:
                run = _Running()
                stats[name] = run
            run.add(value)

    def _update_correlations(self, values: Dict[str, float]) -> None:
        """Slow exponential moving statistics, so structural questions can be
        asked over minutes rather than over one learning cycle."""
        now = time.time()
        dt = max(0.0, now - self._decay_last)
        self._decay_last = now
        alpha = 1.0 - math.exp(-dt / _CORRELATION_HALFLIFE) if dt > 0 else 0.02
        alpha = max(0.01, min(0.25, alpha))

        names = sorted(values)
        for name in names:
            x = values[name] / 100.0
            mean = self._mean.get(name)
            if mean is None:
                self._mean[name] = x
                self._var[name] = 0.0
                continue
            self._mean[name] = mean + alpha * (x - mean)
            deviation = x - self._mean[name]
            self._var[name] = (1 - alpha) * self._var.get(name, 0.0) + alpha * deviation * deviation

        for i, n1 in enumerate(names):
            d1 = values[n1] / 100.0 - self._mean.get(n1, 0.5)
            for n2 in names[i + 1:]:
                d2 = values[n2] / 100.0 - self._mean.get(n2, 0.5)
                key = (n1, n2)
                self._co[key] = (1 - alpha) * self._co.get(key, 0.0) + alpha * d1 * d2

    def correlation(self, a: str, b: str) -> float:
        """Long-run correlation between two neurons, in [-1, 1]."""
        if a == b:
            return 1.0
        key = (a, b) if a < b else (b, a)
        cov = self._co.get(key)
        if cov is None:
            return 0.0
        va = self._var.get(a, 0.0)
        vb = self._var.get(b, 0.0)
        if va < 1e-6 or vb < 1e-6:
            return 0.0
        return max(-1.0, min(1.0, cov / math.sqrt(va * vb)))

    # ==================================================================
    # Diagnosis
    # ==================================================================
    def evaluate(self) -> List[Deficit]:
        """Run every detector and update persistence. Cheap enough for a timer."""
        brain = self.brain
        if brain is None:
            return []

        self.evaluations += 1
        found: List[Deficit] = []
        for detector in (self._detect_connectivity, self._detect_regulation,
                         self._detect_representation, self._detect_expression,
                         self._detect_differentiation):
            try:
                found.extend(detector())
            except Exception as exc:   # a broken detector must not stop the brain
                print(f"[Capability] {detector.__name__} failed: "
                      f"{type(exc).__name__}: {exc}")

        now = time.time()
        seen_keys = set()
        for deficit in found:
            seen_keys.add(deficit.key)
            existing = self.active.get(deficit.key)
            if existing is None:
                deficit.first_seen = now
                deficit.last_seen = now
                deficit.observations = 1
                deficit.initial_severity = deficit.severity
                self.active[deficit.key] = deficit
            else:
                existing.summary = deficit.summary
                existing.severity = deficit.severity
                existing.evidence = deficit.evidence
                existing.sources = deficit.sources
                existing.remedy = deficit.remedy
                existing.target = deficit.target
                existing.suggested_type = deficit.suggested_type
                existing.specialization = deficit.specialization
                existing.last_seen = now
                existing.observations += 1

        for key in [k for k in self.active if k not in seen_keys]:
            gone = self.active.pop(key)
            self.resolved.append((now, gone.kind, gone.summary))

        self.last_evaluation = list(self.active.values())
        return self.last_evaluation

    def actionable(self) -> List[Deficit]:
        """Deficits that have earned new structure.

        Persistent, severe, and not already being fixed by ordinary learning.
        """
        cfg = self.config
        out = [d for d in self.active.values()
               if d.observations >= cfg.min_observations
               and d.age >= cfg.min_age
               and d.severity >= cfg.min_severity
               and d.unresolved]
        out.sort(key=lambda d: -d.severity)
        return out

    def clear(self, key: str, reason: str = "resolved by new structure") -> None:
        deficit = self.active.pop(key, None)
        if deficit is not None:
            self.resolved.append((time.time(), deficit.kind, reason))

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------
    def _neuron_names(self) -> List[str]:
        return list(getattr(self.brain, 'neuron_positions', {}) or {})

    def _weights(self) -> Dict[Tuple[str, str], float]:
        return getattr(self.brain, 'weights', {}) or {}

    def _excluded(self) -> Set[str]:
        return set(getattr(self.brain, 'excluded_neurons', []) or [])

    # -- connectivity ---------------------------------------------------
    def _detect_connectivity(self) -> List[Deficit]:
        brain = self.brain
        if not hasattr(brain, 'find_orphan_neurons'):
            return []
        orphans = brain.find_orphan_neurons() or []
        out = []
        for name in orphans:
            out.append(Deficit(
                kind='connectivity', key=f"connectivity:{name}",
                summary=(f"{name.replace('_', ' ')} has no working connections, so "
                         f"nothing it computes can reach the rest of the brain"),
                target=name, sources=[name],
                remedy=f"give {name.replace('_', ' ')} a route back into the network",
                severity=0.9,
                evidence={'orphan': name},
                suggested_type='connector', specialization='connectivity_bridge'))
        return out

    # -- regulation -----------------------------------------------------
    def _detect_regulation(self) -> List[Deficit]:
        cfg = self.config
        weights = self._weights()
        state = getattr(self.brain, 'state', {}) or {}
        out: List[Deficit] = []

        for stat, (low, high) in COMFORT_BANDS.items():
            history = self._band_history.get(stat)
            if not history or len(history) < min(60, cfg.regulation_window // 2):
                continue
            fraction = sum(1 for bad in history if bad) / len(history)
            if fraction < cfg.out_of_band_fraction:
                continue

            value = state.get(stat)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            too_high = value > high
            if not too_high and value >= low:
                continue     # currently fine; the history is stale
            needed = -1.0 if too_high else 1.0

            # What corrective push does the existing structure actually supply?
            #
            # Measured over the SAME window as the out-of-band fraction above,
            # using each source's mean activation. Reading the sources at the
            # instant of evaluation compared a 240-tick complaint against a
            # one-moment defence: a synapse that corrects hard whenever the
            # drive spikes read as useless whenever the monitor happened to
            # look during a quiet stretch, and the brain grew a neuron it did
            # not need.
            corrective = 0.0
            saturated = 0
            contributors = 0
            for (src, dst), weight in weights.items():
                if dst != stat:
                    continue
                source = self._global.get(src)
                if source is not None and source.n >= 2:
                    src_value = source.mean
                else:
                    src_value = state.get(src)
                    if isinstance(src_value, bool):
                        src_value = 100.0 if src_value else 0.0
                    if not isinstance(src_value, (int, float)):
                        continue
                push = ((float(src_value) - 50.0) / 100.0) * float(weight)
                if push * needed > 0:
                    corrective += abs(push)
                    contributors += 1
                    if abs(float(weight)) >= SATURATION:
                        saturated += 1

            # Is the network actually getting on top of it?
            #
            # The deciding question is not how big the corrective push is - any
            # threshold on that is a magic number, and one that compared a
            # 240-tick complaint against a one-moment defence. It is whether
            # the drive is coming back. The band history covers the same window
            # as the complaint, so its own trend answers it: if the drive was
            # out of band less often in the recent half than the earlier half,
            # existing structure is working and needs time, not company.
            half = len(history) // 2
            earlier = sum(1 for bad in list(history)[:half] if bad) / max(1, half)
            recent = sum(1 for bad in list(history)[half:] if bad) / max(1, len(history) - half)
            improving = recent < earlier - 0.1
            if improving and corrective > 0:
                continue

            excess = abs(value - (high if too_high else low)) / 100.0
            severity = min(1.0, 0.35 + fraction * 0.4 + excess * 0.5)

            drivers = self._correlated_with(stat, exclude={stat}, limit=3)
            direction = "down" if too_high else "up"
            if contributors == 0:
                gap = "there is no synapse at all that pushes it that way"
            elif saturated:
                gap = (f"the {saturated} synapse(s) that push it that way are "
                       f"already at full strength and it is not coming back")
            elif corrective < MIN_CORRECTIVE_PUSH:
                gap = (f"the existing synapses only supply {corrective:.2f} of "
                       f"corrective push and it is not coming back")
            else:
                gap = (f"the existing synapses supply {corrective:.2f} of "
                       f"corrective push and it is still not coming back")

            out.append(Deficit(
                kind='regulation', key=f"regulation:{stat}:{direction}",
                summary=(f"{stat} has been outside its comfortable range for "
                         f"{fraction:.0%} of the last {len(history)} ticks "
                         f"(currently {value:.0f}), and {gap}"),
                target=stat, sources=drivers or [stat],
                remedy=(f"pull {stat} {direction} whenever the situations that "
                        f"drive it appear"),
                severity=severity,
                evidence={'stat': stat, 'value': round(float(value), 1),
                          'out_of_band_fraction': round(fraction, 3),
                          'earlier_half': round(earlier, 3),
                          'recent_half': round(recent, 3),
                          'corrective_push': round(corrective, 3),
                          'saturated_synapses': saturated,
                          'contributors': contributors,
                          'direction': direction},
                suggested_type='stress' if too_high and stat in ('anxiety', 'hunger', 'sleepiness')
                               else ('stress' if not too_high and stat == 'cleanliness' else 'reward'),
                specialization=regulation_specialisation(stat, too_high)))
        return out

    _regulation_specialisation = staticmethod(regulation_specialisation)

    def _correlated_with(self, stat: str, exclude: Optional[Set[str]] = None,
                         limit: int = 3) -> List[str]:
        exclude = exclude or set()
        names = [n for n in self._neuron_names()
                 if n not in exclude and n not in self._excluded()]
        scored = [(abs(self.correlation(stat, n)), n) for n in names]
        scored = [(r, n) for r, n in scored if r >= 0.2]
        scored.sort(reverse=True)
        return [n for _, n in scored[:limit]]

    # -- representation -------------------------------------------------
    def _detect_representation(self) -> List[Deficit]:
        cfg = self.config
        out: List[Deficit] = []
        if self.ticks < _MIN_TICKS_FOR_STATS:
            return out
        excluded = self._excluded()
        network_names = [n for n in self._neuron_names() if n not in excluded]

        for signature, entry in self._signatures.items():
            if entry['count'] < cfg.signature_recurrence:
                continue
            defining = set(entry['defining'])
            stats: Dict[str, _Running] = entry['stats']

            best_d = 0.0
            best_neuron = ""
            for name in network_names:
                # A sensor that defines the situation trivially "discriminates"
                # it; that is not the brain representing anything.
                if name in defining or name in PURE_INPUT_NEURONS:
                    continue
                inside = stats.get(name)
                whole = self._global.get(name)
                if inside is None or whole is None or inside.n < 3:
                    continue
                outside_n = whole.n - inside.n
                if outside_n < 5:
                    continue
                outside_mean = (whole.total - inside.total) / outside_n
                outside_sq = (whole.total_sq - inside.total_sq) / outside_n
                outside_var = max(0.0, outside_sq - outside_mean ** 2)
                pooled = math.sqrt(max(1.0, (inside.var + outside_var) / 2.0))
                d = abs(inside.mean - outside_mean) / pooled
                if d > best_d:
                    best_d = d
                    best_neuron = name

            if best_d >= cfg.discriminability_floor:
                continue    # something already represents it

            severity = min(1.0, 0.4 + min(1.0, entry['count'] / 30.0) * 0.4
                           + (cfg.discriminability_floor - best_d) * 0.3)
            readable = signature.replace('|', ' and ').replace('_', ' ')
            out.append(Deficit(
                kind='representation', key=f"representation:{signature}",
                summary=(f"the situation '{readable}' has come round "
                         f"{entry['count']} times, and no neuron in the brain "
                         f"fires any differently when it does "
                         f"(best separation {best_d:.2f}"
                         + (f", from {best_neuron}" if best_neuron else "") + ")"),
                target=signature,
                sources=[n for n in entry['defining']
                         if n in self._neuron_names()][:4],
                remedy=f"fire specifically when '{readable}' is the case",
                severity=severity,
                evidence={'signature': signature, 'occurrences': entry['count'],
                          'best_discriminability': round(best_d, 3),
                          'best_neuron': best_neuron,
                          'defining': list(entry['defining'])},
                suggested_type='novelty',
                specialization=self._representation_specialisation(entry['defining'])))
        return out

    @staticmethod
    def _representation_specialisation(defining: Iterable[str]) -> str:
        joined = " ".join(defining).lower()
        if 'plant' in joined or 'external_stimulus' in joined:
            return 'object_investigation'
        if 'food' in joined or 'eating' in joined:
            return 'feeding_satisfaction'
        if 'sick' in joined or 'threat' in joined or 'startled' in joined or 'fleeing' in joined:
            return 'general_stress_coping'
        if 'sleeping' in joined:
            return 'rest_reward'
        return 'general_novelty_processing'

    # -- expression -----------------------------------------------------
    def _detect_expression(self) -> List[Deficit]:
        causal = getattr(self.brain, 'causal_learning', None)
        if causal is None or not hasattr(causal, 'cue_outcome_links'):
            return []
        weights = self._weights()
        names = set(self._neuron_names())
        out: List[Deficit] = []

        for cue, action, stat, confidence in causal.cue_outcome_links():
            if cue not in names or stat not in names:
                continue
            entry = causal.contingencies.get(action, {}).get(stat)
            if entry is None:
                continue
            effect = entry.effect(causal.baseline_drift(stat))
            if abs(effect) < 1.0:
                continue
            wanted = 1.0 if effect > 0 else -1.0

            if self._has_usable_path(weights, cue, stat, wanted):
                continue

            direction = "up" if wanted > 0 else "down"
            severity = min(1.0, 0.4 + confidence * 0.5)
            out.append(Deficit(
                kind='expression', key=f"expression:{cue}->{stat}",
                summary=(f"the squid has worked out that {cue.replace('_', ' ')} plus "
                         f"{action.replace('_', ' ')} sends {stat} {direction} by "
                         f"{abs(effect):.0f} ({confidence:.0%} confident), but there is "
                         f"no pathway in the network from {cue.replace('_', ' ')} to "
                         f"{stat} that could act on it"),
                target=stat, sources=[cue],
                remedy=(f"carry {cue.replace('_', ' ')} through to {stat} so the squid "
                        f"can act on what it worked out"),
                severity=severity,
                evidence={'cue': cue, 'action': action, 'stat': stat,
                          'effect': round(effect, 2),
                          'confidence': round(confidence, 3),
                          'wanted_sign': wanted},
                suggested_type='reward' if wanted > 0 else 'stress',
                specialization='learned_expectation'))
        return out

    @staticmethod
    def _has_usable_path(weights: Dict[Tuple[str, str], float], cue: str,
                         stat: str, wanted: float) -> bool:
        """Is there a synaptic route from cue to stat with the right sign and
        room left to grow?"""
        direct = weights.get((cue, stat))
        if direct is not None and abs(direct) >= 0.15 and direct * wanted > 0:
            if abs(direct) < SATURATION:
                return True
            # Saturated but correct: the pathway exists and is doing all it can.
            return True
        for (src, mid), w1 in weights.items():
            if src != cue or abs(w1) < 0.15:
                continue
            w2 = weights.get((mid, stat))
            if w2 is None or abs(w2) < 0.15:
                continue
            if (w1 * w2) * wanted > 0:
                return True
        return False

    # -- differentiation ------------------------------------------------
    def _detect_differentiation(self) -> List[Deficit]:
        cfg = self.config
        if self.ticks < _MIN_TICKS_FOR_STATS:
            return []
        weights = self._weights()
        excluded = self._excluded()
        incoming: Dict[str, List[Tuple[str, float]]] = {}
        for (src, dst), weight in weights.items():
            if dst in excluded or abs(float(weight)) < cfg.conflict_weight:
                continue
            incoming.setdefault(dst, []).append((src, float(weight)))

        out: List[Deficit] = []
        for target, drivers in incoming.items():
            if len(drivers) < 2 or not is_learning_target(target):
                continue
            worst = 0.0
            pair: Optional[Tuple[str, str]] = None
            for i, (a, _wa) in enumerate(drivers):
                for b, _wb in drivers[i + 1:]:
                    r = self.correlation(a, b)
                    if r < worst:
                        worst = r
                        pair = (a, b)
            if pair is None or worst > cfg.conflict_correlation:
                continue

            a, b = pair
            severity = min(1.0, 0.35 + abs(worst) * 0.6)
            out.append(Deficit(
                kind='differentiation', key=f"differentiation:{target}:{a}:{b}",
                summary=(f"{target.replace('_', ' ')} is driven by both "
                         f"{a.replace('_', ' ')} and {b.replace('_', ' ')}, which "
                         f"pull in opposite directions (correlation {worst:+.2f}); "
                         f"one neuron cannot stand for both situations at once"),
                target=target, sources=[b],
                remedy=(f"take {b.replace('_', ' ')} off {target.replace('_', ' ')} "
                        f"and represent it separately"),
                severity=severity,
                evidence={'target': target, 'conflicting': [a, b],
                          'correlation': round(worst, 3)},
                suggested_type='novelty', specialization='role_separation'))
        return out

    # ==================================================================
    # Reporting
    # ==================================================================
    def report(self) -> Dict[str, Any]:
        return {
            'ticks': self.ticks,
            'evaluations': self.evaluations,
            'signatures_tracked': len(self._signatures),
            'active': [d.to_dict() for d in
                       sorted(self.active.values(), key=lambda d: -d.severity)],
            'actionable': [d.key for d in self.actionable()],
            'recently_resolved': [{'at': at, 'kind': kind, 'why': why}
                                  for at, kind, why in list(self.resolved)[-8:]],
        }

    def describe(self) -> str:
        deficits = sorted(self.active.values(), key=lambda d: -d.severity)
        if not deficits:
            return "The network can currently represent, regulate and express everything it has met."
        lines = []
        for d in deficits:
            state = ("ready to grow structure" if d in self.actionable()
                     else f"watching ({d.observations} observation(s), "
                          f"{d.age:.0f}s)")
            lines.append(f"[{d.kind}] {d.summary} — severity {d.severity:.2f}, {state}")
        return "\n".join(lines)

    # ==================================================================
    # Persistence
    # ==================================================================
    def to_dict(self) -> dict:
        return {
            'ticks': self.ticks,
            'evaluations': self.evaluations,
            'active': [d.to_dict() for d in self.active.values()],
            'global': {k: v.to_dict() for k, v in self._global.items()},
            'signatures': {
                sig: {'count': e['count'], 'first_seen': e['first_seen'],
                      'last_seen': e['last_seen'], 'defining': list(e['defining']),
                      'stats': {k: v.to_dict() for k, v in e['stats'].items()}}
                for sig, e in self._signatures.items()},
            'mean': dict(self._mean),
            'var': dict(self._var),
            'co': [[a, b, v] for (a, b), v in self._co.items()],
            'bands': {k: list(v) for k, v in self._band_history.items()},
        }

    def from_dict(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        self.ticks = int(data.get('ticks', 0))
        self.evaluations = int(data.get('evaluations', 0))
        self.active = {}
        for raw in data.get('active') or []:
            try:
                deficit = Deficit.from_dict(raw)
            except Exception:
                continue
            if deficit.key:
                self.active[deficit.key] = deficit
        self._global = {str(k): _Running.from_dict(v)
                        for k, v in (data.get('global') or {}).items()}
        self._signatures = {}
        for sig, raw in (data.get('signatures') or {}).items():
            self._signatures[str(sig)] = {
                'count': int(raw.get('count', 0)),
                'first_seen': float(raw.get('first_seen', 0.0)),
                'last_seen': float(raw.get('last_seen', 0.0)),
                'defining': list(raw.get('defining') or []),
                'stats': {str(k): _Running.from_dict(v)
                          for k, v in (raw.get('stats') or {}).items()},
            }
        self._mean = {str(k): float(v) for k, v in (data.get('mean') or {}).items()}
        self._var = {str(k): float(v) for k, v in (data.get('var') or {}).items()}
        self._co = {}
        for row in data.get('co') or []:
            if isinstance(row, (list, tuple)) and len(row) == 3:
                self._co[(str(row[0]), str(row[1]))] = float(row[2])
        self._band_history = {}
        for stat, values in (data.get('bands') or {}).items():
            self._band_history[str(stat)] = deque(
                [bool(v) for v in values], maxlen=self.config.regulation_window)

    def reset(self) -> None:
        self.ticks = 0
        self.evaluations = 0
        self._global.clear()
        self._signatures.clear()
        self._co.clear()
        self._mean.clear()
        self._var.clear()
        self._band_history.clear()
        self.active.clear()
        self.resolved.clear()
        self.last_evaluation = []
