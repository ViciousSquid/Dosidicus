"""
neural_provenance.py - the brain's own record of why it is the way it is.

Dosidicus claims that "every learned behaviour can be traced back to
experience". Until now nothing in the engine actually stored that trace: a
weight moved from 0.31 to 0.47 and the reason evaporated, and the UI had to
guess after the fact by diffing its own cached copy of the weights.

This module is the missing memory. It is owned by the brain (not by the UI),
it is written by the mechanisms that actually change the network - plasticity,
STDP, sleep consolidation, causal learning, neurogenesis, the Designer - and
it is saved with the squid. Everything the inspection tools display is read
from here, so the picture the player sees is the organism's own record rather
than a reconstruction of it.

It answers four questions directly:

    "Why did this weight change from 0.31 to 0.47?"   explain_weight()
    "Why does this neuron exist?"                      explain_neuron()
    "What does the squid know about food?"             knowledge('food')
    "What experience caused it to learn this?"         KnowledgeItem.experience

Design notes
------------
* Bounded. A squid can run for weeks; every history is a deque with a cap, and
  the per-edge running totals survive after individual events age out, so
  "0.31 -> 0.47" is still explainable long after the events themselves are gone.
* Non-authoritative for state. The ledger never holds a second copy of the
  weights or activations - it reads brain.weights / brain.state live. It only
  owns history, which nothing else has.
* Total. Every write to brain.weights should go through
  BrainWidget.apply_weight_change() so that no change is unaccounted for.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

Pair = Tuple[str, str]


# ---------------------------------------------------------------------------
# Mechanisms: the complete set of things that are allowed to move a synapse.
# The phrasing is what the player reads, so keep it plain.
# ---------------------------------------------------------------------------
MECHANISMS: Dict[str, str] = {
    'hebbian':       "they kept happening together",
    'stdp':          "one reliably fired just before the other",
    'causal_reward': "an action it took led to a result worth repeating",
    'consolidation': "it was replayed during sleep",
    'neurogenesis':  "a new neuron was wired in",
    'designer':      "you wired it by hand",
    'innate':        "it was born with it",
    'reflex':        "an innate reflex fired",
    'prune':         "it never amounted to anything and was pruned",
    'decay':         "it faded from disuse",
    'manual':        "it was set directly",
}

# How a deficit is described to the player. Mirrors capability.DEFICIT_KINDS.
DEFICIT_PHRASING: Dict[str, str] = {
    'representation': "the brain had no neuron that could tell this situation apart from any other",
    'regulation':     "the brain could not pull this feeling back to a comfortable level",
    'expression':     "the brain had learned something it had no pathway to act on",
    'differentiation': "one neuron was being asked to stand for two unrelated things at once",
    'connectivity':   "part of the network had been left unreachable",
    'causal_differentiation':
        "the brain had no way to represent which of two things that always "
        "happen together was the one actually causing the outcome",
}

_MAX_EVENTS_PER_EDGE = 24
_MAX_RECENT_EVENTS = 400

# A change smaller than this is accounted for but not narrated.
#
# Some mechanisms are high-frequency and small: an outcome touches every
# synapse that was participating, many times a minute, by thousandths. Those
# are real and their totals must be exact, but four hundred lines of "+0.002
# because an action led to a result worth repeating" bury the handful of
# changes that actually tell the squid's story - and push them out of the
# bounded event list entirely. The running totals below are unaffected, so
# "why is this weight 0.47" still adds up exactly.
_NARRATABLE_DELTA = 0.005

# Changes that are always worth narrating whatever their size, because they
# say something structural rather than incremental.
_ALWAYS_NARRATE = {'neurogenesis', 'designer', 'prune', 'innate'}
_MAX_EPISODES = 200
_MAX_DECISIONS = 120
_MAX_PRUNED = 60


def humanise(name: str) -> str:
    """A neuron name a person can read."""
    if not name:
        return "?"
    return str(name).replace('_', ' ').strip()


def _strength_word(weight: float) -> str:
    a = abs(weight)
    if a >= 0.65:
        return "strongly"
    if a >= 0.3:
        return "clearly"
    if a >= 0.12:
        return "slightly"
    return "barely"


def _confidence_word(confidence: float) -> str:
    if confidence >= 0.75:
        return "very confident"
    if confidence >= 0.5:
        return "confident"
    if confidence >= 0.25:
        return "tentative"
    return "just a hunch"


def _fmt_time(ts: Optional[float]) -> str:
    if not ts:
        return "unknown"
    return time.strftime('%H:%M:%S', time.localtime(ts))


def _fmt_ago(ts: Optional[float], now: Optional[float] = None) -> str:
    if not ts:
        return "at some point"
    now = now or time.time()
    dt = max(0.0, now - ts)
    if dt < 60:
        return f"{int(dt)}s ago"
    if dt < 3600:
        return f"{int(dt // 60)} min ago"
    if dt < 86400:
        return f"{int(dt // 3600)}h ago"
    return f"{int(dt // 86400)}d ago"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
@dataclass
class Episode:
    """One thing that happened to the squid, with its consequence.

    Written by causal_learning.ActionOutcomeLedger when an action's outcome
    window closes, and referenced by every weight change that action caused.
    """
    episode_id: str
    action: str
    started: float
    ended: float = 0.0
    cue: Dict[str, float] = field(default_factory=dict)
    consequence: Dict[str, float] = field(default_factory=dict)
    valence: float = 0.0
    note: str = ""

    def describe(self) -> str:
        cue_bits = ", ".join(
            f"{humanise(k)} was {v:.0f}" for k, v in sorted(
                self.cue.items(), key=lambda kv: -abs(kv[1] - 50.0))[:3])
        out_bits = ", ".join(
            f"{humanise(k)} {'rose' if d > 0 else 'fell'} {abs(d):.0f}"
            for k, d in sorted(self.consequence.items(),
                               key=lambda kv: -abs(kv[1]))[:3] if abs(d) >= 0.5)
        # "it was doing eating" rather than "it eating": an action name is a
        # label, not a verb, and English does not conjugate it for us.
        parts = [f"it was doing {humanise(self.action)}"]
        if cue_bits:
            parts.append(f"while {cue_bits}")
        if out_bits:
            parts.append(f"and then {out_bits}")
        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            'episode_id': self.episode_id, 'action': self.action,
            'started': self.started, 'ended': self.ended, 'cue': self.cue,
            'consequence': self.consequence, 'valence': self.valence,
            'note': self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Episode':
        return cls(
            episode_id=str(d.get('episode_id', '')),
            action=str(d.get('action', 'something')),
            started=float(d.get('started', 0.0)),
            ended=float(d.get('ended', 0.0)),
            cue={k: float(v) for k, v in (d.get('cue') or {}).items()},
            consequence={k: float(v) for k, v in (d.get('consequence') or {}).items()},
            valence=float(d.get('valence', 0.0)),
            note=str(d.get('note', '')),
        )


@dataclass
class WeightEvent:
    """One synaptic change, with the reason it happened."""
    edge: Pair
    old_weight: float
    new_weight: float
    mechanism: str
    timestamp: float
    detail: Dict[str, Any] = field(default_factory=dict)
    episode_id: Optional[str] = None

    @property
    def delta(self) -> float:
        return self.new_weight - self.old_weight

    def describe(self) -> str:
        src, dst = self.edge
        direction = "strengthened" if self.delta > 0 else "weakened"
        reason = MECHANISMS.get(self.mechanism, self.mechanism)
        line = (f"{_fmt_time(self.timestamp)}  {humanise(src)} → {humanise(dst)} "
                f"{direction} {self.old_weight:+.3f} → {self.new_weight:+.3f} "
                f"({self.delta:+.3f}) because {reason}")
        bits = []
        r = self.detail.get('correlation')
        if isinstance(r, (int, float)):
            bits.append(f"correlation {r:+.2f}")
        n = self.detail.get('samples')
        if isinstance(n, int) and n:
            bits.append(f"over {n} observations")
        s = self.detail.get('stdp_delta')
        if isinstance(s, (int, float)) and s:
            bits.append(f"spike-timing {s:+.3f}")
        if self.detail.get('note'):
            bits.append(str(self.detail['note']))
        if bits:
            line += " — " + ", ".join(bits)
        return line

    def to_dict(self) -> dict:
        return {
            'edge': list(self.edge), 'old': self.old_weight, 'new': self.new_weight,
            'mechanism': self.mechanism, 'timestamp': self.timestamp,
            'detail': self.detail, 'episode_id': self.episode_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Optional['WeightEvent']:
        edge = d.get('edge') or []
        if len(edge) != 2:
            return None
        return cls(
            edge=(str(edge[0]), str(edge[1])),
            old_weight=float(d.get('old', 0.0)),
            new_weight=float(d.get('new', 0.0)),
            mechanism=str(d.get('mechanism', 'manual')),
            timestamp=float(d.get('timestamp', 0.0)),
            detail=dict(d.get('detail') or {}),
            episode_id=d.get('episode_id'),
        )


@dataclass
class NeuronOrigin:
    """Why a neuron exists. Written once, at birth, and never rewritten."""
    name: str
    created_at: float
    deficit_kind: str
    deficit_summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    remedy: str = ""
    wiring: List[Tuple[str, str, float, str]] = field(default_factory=list)
    episode_ids: List[str] = field(default_factory=list)
    neuron_type: str = ""
    specialization: str = ""
    display_name: str = ""
    pruned_at: Optional[float] = None
    prune_reason: str = ""

    def describe(self) -> str:
        label = self.display_name or humanise(self.name)
        why = DEFICIT_PHRASING.get(self.deficit_kind, self.deficit_kind)
        lines = [f"{label} was grown {_fmt_ago(self.created_at)} because {why}."]
        if self.deficit_summary:
            lines.append(f"Specifically: {self.deficit_summary}")
        if self.remedy:
            lines.append(f"It was wired to {self.remedy}")
        if self.wiring:
            wired = ", ".join(f"{humanise(a)} → {humanise(b)} at {w:+.2f}"
                              for a, b, w, _ in self.wiring[:6])
            lines.append(f"Connections made at birth: {wired}.")
        if self.pruned_at:
            lines.append(f"It was pruned {_fmt_ago(self.pruned_at)} "
                         f"({self.prune_reason or 'low utility'}).")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            'name': self.name, 'created_at': self.created_at,
            'deficit_kind': self.deficit_kind, 'deficit_summary': self.deficit_summary,
            'evidence': self.evidence, 'remedy': self.remedy,
            'wiring': [list(w) for w in self.wiring],
            'episode_ids': list(self.episode_ids),
            'neuron_type': self.neuron_type, 'specialization': self.specialization,
            'display_name': self.display_name,
            'pruned_at': self.pruned_at, 'prune_reason': self.prune_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'NeuronOrigin':
        wiring = []
        for w in d.get('wiring') or []:
            if isinstance(w, (list, tuple)) and len(w) >= 3:
                wiring.append((str(w[0]), str(w[1]), float(w[2]),
                               str(w[3]) if len(w) > 3 else ""))
        return cls(
            name=str(d.get('name', '')),
            created_at=float(d.get('created_at', 0.0)),
            deficit_kind=str(d.get('deficit_kind', 'representation')),
            deficit_summary=str(d.get('deficit_summary', '')),
            evidence=dict(d.get('evidence') or {}),
            remedy=str(d.get('remedy', '')),
            wiring=wiring,
            episode_ids=list(d.get('episode_ids') or []),
            neuron_type=str(d.get('neuron_type', '')),
            specialization=str(d.get('specialization', '')),
            display_name=str(d.get('display_name', '')),
            pruned_at=d.get('pruned_at'),
            prune_reason=str(d.get('prune_reason', '')),
        )


@dataclass
class KnowledgeItem:
    """One thing the squid knows, in plain English, with its whole provenance."""
    subject: str                 # what it is about, e.g. "food"
    statement: str               # what it learned
    experience: str              # what experience caused it
    action: str                  # which action was involved ("" if none)
    consequence: str             # what consequence followed
    reason: str                  # why the connection was strengthened / weakened
    confidence: float            # 0..1
    strength: float              # the synaptic weight, or effect size
    behaviour: str               # how the knowledge has affected behaviour
    kind: str = 'association'    # association | contingency | structure
    edge: Optional[Pair] = None
    neuron: Optional[str] = None
    updated: float = 0.0

    def describe(self) -> str:
        lines = [self.statement]
        if self.experience:
            lines.append(f"  Learned from: {self.experience}")
        if self.action:
            lines.append(f"  Action involved: {humanise(self.action)}")
        if self.consequence:
            lines.append(f"  Consequence: {self.consequence}")
        if self.reason:
            lines.append(f"  Why it changed: {self.reason}")
        lines.append(f"  Confidence: {self.confidence:.0%} ({_confidence_word(self.confidence)}), "
                     f"strength {self.strength:+.2f}")
        if self.behaviour:
            lines.append(f"  Effect on behaviour: {self.behaviour}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        if self.edge:
            d['edge'] = list(self.edge)
        return d


# ---------------------------------------------------------------------------
# The write path
# ---------------------------------------------------------------------------
class RecordedSynapses:
    """The one way a synapse is allowed to change.

    Mixed into anything that owns a `weights` dict and a `ledger`: the game's
    BrainWidget and the headless trainer's HeadlessBrain both use this exact
    implementation, so "record every change" cannot be true in one and subtly
    false in the other. Test doubles get it for free, which means a double
    cannot silently exercise a path production does not have.

    Presentation is the only thing subclasses add, through the two hooks at the
    bottom. Nothing else about a weight change is theirs to vary.
    """

    weights: Dict[Pair, float]

    def apply_weight_change(self, edge, delta: Optional[float] = None,
                            value: Optional[float] = None,
                            mechanism: str = 'manual',
                            detail: Optional[dict] = None,
                            episode_id: Optional[str] = None,
                            create: bool = True, animate: bool = True,
                            directed: bool = True) -> bool:
        """Change one synapse and record the reason.

        Pass `delta` to nudge the existing weight or `value` to set it outright.
        Returns True if the weight actually moved.

        `directed` says whether the caller means this exact synapse. It must,
        for anything structural: a regulator neuron is wired
        drive -> regulator excitatory AND regulator -> drive inhibitory, and
        collapsing those onto one undirected edge silently destroys the second
        one - the whole point of the neuron. Callers that hold an unordered
        pair (an innate reflex, a direct co-activation update) pass
        directed=False and get the existing synapse in whichever direction it
        already runs.
        """
        if not (isinstance(edge, tuple) and len(edge) == 2):
            return False
        src, dst = edge
        if src == dst:
            return False

        existing = edge in self.weights
        if not existing and not directed:
            reverse = (dst, src)
            if reverse in self.weights:
                edge = reverse
                src, dst = edge
                existing = True

        if not existing and not create:
            return False

        old = float(self.weights.get(edge, 0.0))
        if value is not None:
            new = float(value)
        elif delta is not None:
            new = old + float(delta)
        else:
            return False

        new = max(-1.0, min(1.0, new))
        if existing and abs(new - old) < 1e-9:
            return False

        self.weights[edge] = new

        ledger = getattr(self, 'ledger', None)
        if ledger is not None:
            ledger.record_weight_change(edge, old, new, mechanism,
                                        detail=detail, episode_id=episode_id)

        self._on_weight_changed(edge, old, new, animate)
        return True

    def remove_weight(self, edge, mechanism: str = 'prune',
                      reason: str = "") -> bool:
        """Delete one synapse, recording why it went."""
        if edge not in self.weights:
            return False
        old = float(self.weights.pop(edge))
        ledger = getattr(self, 'ledger', None)
        if ledger is not None:
            ledger.record_weight_change(edge, old, 0.0, mechanism,
                                        detail={'note': reason or 'removed',
                                                'removed': True})
        self._on_weight_removed(edge, old)
        return True

    # -- questions any brain can answer about itself --------------------
    def explain_weight(self, edge, from_value=None, to_value=None) -> str:
        ledger = getattr(self, 'ledger', None)
        if ledger is None:
            return "This brain keeps no provenance."
        return ledger.explain_weight(tuple(edge), from_value, to_value)

    def explain_neuron(self, name: str) -> str:
        ledger = getattr(self, 'ledger', None)
        if ledger is None:
            return "This brain keeps no provenance."
        return ledger.explain_neuron(name)

    def what_do_you_know(self, topic: Optional[str] = None, limit: int = 60):
        ledger = getattr(self, 'ledger', None)
        if ledger is None:
            return []
        return ledger.knowledge(topic, limit=limit)

    # -- presentation hooks ---------------------------------------------
    def _on_weight_changed(self, edge: Pair, old: float, new: float,
                           animate: bool) -> None:
        """Called after the change is recorded. Override to draw it."""

    def _on_weight_removed(self, edge: Pair, old: float) -> None:
        """Called after the removal is recorded. Override to draw it."""


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------
class CausalLedger:
    """Provenance for one brain. Owned by BrainWidget, saved with the squid."""

    def __init__(self, brain=None):
        self.brain = brain

        self._events_by_edge: Dict[Pair, Deque[WeightEvent]] = {}
        self._recent: Deque[WeightEvent] = deque(maxlen=_MAX_RECENT_EVENTS)

        # Running totals survive after individual events age out, so a synapse
        # is still explainable months into a squid's life.
        self._totals: Dict[Pair, Dict[str, float]] = {}
        self._counts: Dict[Pair, Dict[str, int]] = {}
        self._first_seen: Dict[Pair, float] = {}

        self.origins: Dict[str, NeuronOrigin] = {}
        self.pruned: Deque[NeuronOrigin] = deque(maxlen=_MAX_PRUNED)
        self.episodes: Deque[Episode] = deque(maxlen=_MAX_EPISODES)
        self._episode_index: Dict[str, Episode] = {}

        # Behaviour attribution: how much each synapse has actually pushed the
        # squid around, and what it decided while it was being pushed.
        self._influence: Dict[Pair, Dict[str, Any]] = {}
        self.decisions: Deque[Tuple[float, str, Dict[str, float]]] = deque(
            maxlen=_MAX_DECISIONS)

        self.display_names: Dict[str, str] = {}
        self.total_changes = 0

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------
    def record_weight_change(self, edge: Pair, old_weight: float, new_weight: float,
                             mechanism: str, detail: Optional[Dict[str, Any]] = None,
                             episode_id: Optional[str] = None,
                             timestamp: Optional[float] = None) -> Optional[WeightEvent]:
        """Record one synaptic change. Returns the event, or None if it was a no-op."""
        try:
            old_weight = float(old_weight)
            new_weight = float(new_weight)
        except (TypeError, ValueError):
            return None
        if not (isinstance(edge, tuple) and len(edge) == 2):
            return None
        if abs(new_weight - old_weight) < 1e-9 and mechanism not in ('prune', 'designer'):
            return None

        event = WeightEvent(edge=edge, old_weight=old_weight, new_weight=new_weight,
                            mechanism=mechanism, timestamp=timestamp or time.time(),
                            detail=dict(detail or {}), episode_id=episode_id)

        if edge not in self._first_seen:
            self._first_seen[edge] = event.timestamp

        # Narrate the changes worth reading; account for all of them.
        crossed_zero = (old_weight > 0) != (new_weight > 0)
        if (abs(event.delta) >= _NARRATABLE_DELTA
                or mechanism in _ALWAYS_NARRATE or crossed_zero):
            bucket = self._events_by_edge.get(edge)
            if bucket is None:
                bucket = deque(maxlen=_MAX_EVENTS_PER_EDGE)
                self._events_by_edge[edge] = bucket
            bucket.append(event)
            self._recent.append(event)

        totals = self._totals.setdefault(edge, {})
        totals[mechanism] = totals.get(mechanism, 0.0) + event.delta
        counts = self._counts.setdefault(edge, {})
        counts[mechanism] = counts.get(mechanism, 0) + 1

        # A synapse that changes sign means the opposite thing from now on, so
        # its behavioural record starts again. Carrying the old total forward
        # produced flat contradictions - "when food is in sight satisfaction
        # goes DOWN ... it has spent 626 ticks raising satisfaction" - because
        # the influence had been accumulated while the weight was positive.
        if crossed_zero:
            self._influence.pop(edge, None)

        self.total_changes += 1
        return event

    def record_neuron_birth(self, name: str, deficit_kind: str, deficit_summary: str,
                            evidence: Optional[Dict[str, Any]] = None, remedy: str = "",
                            wiring: Optional[Iterable[Tuple[str, str, float, str]]] = None,
                            episode_ids: Optional[Iterable[str]] = None,
                            neuron_type: str = "", specialization: str = "",
                            display_name: str = "",
                            timestamp: Optional[float] = None) -> NeuronOrigin:
        origin = NeuronOrigin(
            name=name, created_at=timestamp or time.time(),
            deficit_kind=deficit_kind, deficit_summary=deficit_summary,
            evidence=dict(evidence or {}), remedy=remedy,
            wiring=[tuple(w) for w in (wiring or [])],
            episode_ids=list(episode_ids or []),
            neuron_type=neuron_type, specialization=specialization,
            display_name=display_name or humanise(name),
        )
        self.origins[name] = origin
        if display_name:
            self.display_names[name] = display_name
        return origin

    def record_neuron_pruned(self, name: str, reason: str = "",
                             timestamp: Optional[float] = None) -> None:
        origin = self.origins.pop(name, None)
        if origin is None:
            origin = NeuronOrigin(name=name, created_at=0.0,
                                  deficit_kind='representation',
                                  deficit_summary="origin not recorded")
        origin.pruned_at = timestamp or time.time()
        origin.prune_reason = reason
        self.pruned.append(origin)

    def rename_neuron(self, old: str, new: str) -> None:
        """Keep provenance attached when a neuron is renamed."""
        if old in self.origins:
            origin = self.origins.pop(old)
            origin.name = new
            self.origins[new] = origin
        if old in self.display_names:
            self.display_names[new] = self.display_names.pop(old)

    def record_episode(self, episode: Episode) -> None:
        self.episodes.append(episode)
        self._episode_index[episode.episode_id] = episode
        # Keep the index bounded alongside the deque.
        if len(self._episode_index) > _MAX_EPISODES * 2:
            live = {e.episode_id for e in self.episodes}
            self._episode_index = {k: v for k, v in self._episode_index.items()
                                   if k in live}

    def get_episode(self, episode_id: Optional[str]) -> Optional[Episode]:
        if not episode_id:
            return None
        return self._episode_index.get(episode_id)

    def record_influence(self, edge: Pair, amount: float, channel: str,
                         target: str = "") -> None:
        """Note that this synapse actually pushed the squid's physiology."""
        if not amount:
            return
        rec = self._influence.setdefault(
            edge, {'total': 0.0, 'net': 0.0, 'channel': channel,
                   'target': target, 'last': 0.0, 'ticks': 0})
        rec['total'] += abs(amount)
        rec['net'] += amount
        rec['channel'] = channel
        rec['target'] = target or rec['target']
        rec['last'] = time.time()
        rec['ticks'] += 1

    def record_decision(self, decision: str, drivers: Optional[Dict[str, float]] = None
                        ) -> None:
        self.decisions.append((time.time(), str(decision), dict(drivers or {})))

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def label(self, name: str) -> str:
        return self.display_names.get(name) or humanise(name)

    def weight_history(self, edge: Pair, limit: int = 20) -> List[WeightEvent]:
        bucket = self._events_by_edge.get(edge)
        if not bucket:
            return []
        return list(bucket)[-limit:]

    def edge_totals(self, edge: Pair) -> Dict[str, float]:
        return dict(self._totals.get(edge, {}))

    def current_weight(self, edge: Pair) -> Optional[float]:
        weights = getattr(self.brain, 'weights', None)
        if isinstance(weights, dict) and edge in weights:
            return float(weights[edge])
        bucket = self._events_by_edge.get(edge)
        if bucket:
            return bucket[-1].new_weight
        return None

    def explain_weight(self, edge: Pair, from_value: Optional[float] = None,
                       to_value: Optional[float] = None) -> str:
        """Plain-English answer to 'why did this weight change?'.

        With from_value/to_value it explains that specific span; without, it
        explains the synapse's whole recorded life.
        """
        src, dst = edge
        label = f"{self.label(src)} → {self.label(dst)}"
        events = self.weight_history(edge, limit=_MAX_EVENTS_PER_EDGE)
        totals = self.edge_totals(edge)
        current = self.current_weight(edge)

        if not events and not totals:
            if current is None:
                return f"There is no synapse {label}, and none is on record."
            return (f"{label} is at {current:+.3f}. It has been there since the brain "
                    f"was built - nothing has changed it, so there is nothing to explain.")

        span = events
        if from_value is not None and to_value is not None:
            span = [e for e in events
                    if min(from_value, to_value) - 1e-6 <= e.old_weight <= max(from_value, to_value) + 1e-6
                    or min(from_value, to_value) - 1e-6 <= e.new_weight <= max(from_value, to_value) + 1e-6]
            if not span:
                span = events

        lines = []
        if span:
            start = span[0].old_weight
            end = span[-1].new_weight
            lines.append(f"{label} moved {start:+.3f} → {end:+.3f} over "
                         f"{len(span)} recorded change(s).")
        elif current is not None:
            lines.append(f"{label} currently sits at {current:+.3f}.")

        if totals:
            ordered = sorted(totals.items(), key=lambda kv: -abs(kv[1]))
            contributions = []
            for mech, amount in ordered:
                if abs(amount) < 1e-4:
                    continue
                n = self._counts.get(edge, {}).get(mech, 0)
                contributions.append(
                    f"{amount:+.3f} from {MECHANISMS.get(mech, mech)} "
                    f"({n} time{'s' if n != 1 else ''})")
            if contributions:
                lines.append("Over its whole life: " + "; ".join(contributions) + ".")

        for event in span[-6:]:
            lines.append("  " + event.describe())
            ep = self.get_episode(event.episode_id)
            if ep is not None:
                lines.append(f"      Experience: {ep.describe()}.")

        infl = self._influence.get(edge)
        if infl and infl.get('ticks'):
            lines.append(
                f"Since then it has pushed {self.label(infl.get('target') or dst)} by "
                f"{infl['net']:+.1f} points in total across {infl['ticks']} ticks, "
                f"which is how it shows up in the squid's behaviour.")
        return "\n".join(lines)

    def explain_neuron(self, name: str) -> str:
        """Plain-English answer to 'why does this neuron exist?'."""
        origin = self.origins.get(name)
        if origin is None:
            for candidate in self.pruned:
                if candidate.name == name:
                    return candidate.describe()
            positions = getattr(self.brain, 'neuron_positions', {}) or {}
            if name in positions:
                from .brain_constants import (CORE_STAT_NEURONS,
                                              PURE_INPUT_NEURONS)
                if name in CORE_STAT_NEURONS:
                    return (f"{self.label(name)} is one of the seven drives every "
                            f"squid is born with. It exists because the squid has a body.")
                if name in PURE_INPUT_NEURONS:
                    return (f"{self.label(name)} is a sense organ the squid was born "
                            f"with. The world writes it; the network reads it.")
                return (f"{self.label(name)} was added outside neurogenesis - most "
                        f"likely hand-wired in the Brain Designer or loaded from a "
                        f"custom brain.")
            return f"There is no neuron called {name}."

        lines = [origin.describe()]
        episodes = [self.get_episode(eid) for eid in origin.episode_ids[:3]]
        episodes = [ep for ep in episodes if ep is not None]
        if episodes:
            lines.append("  What the squid was living through at the time:")
            for ep in episodes:
                lines.append(f"    · {ep.describe()}.")

        weights = getattr(self.brain, 'weights', {}) or {}
        live = [(e, w) for e, w in weights.items() if name in e and abs(w) >= 0.05]
        if live:
            live.sort(key=lambda item: -abs(item[1]))
            wired = ", ".join(f"{self.label(a)} → {self.label(b)} {w:+.2f}"
                              for (a, b), w in live[:6])
            lines.append(f"It is currently wired: {wired}.")
        else:
            lines.append("It currently has no meaningful connections.")

        state = getattr(self.brain, 'state', {}) or {}
        if name in state and isinstance(state[name], (int, float)):
            lines.append(f"Right now it is firing at {float(state[name]):.0f}/100.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Knowledge synthesis
    # ------------------------------------------------------------------
    def _confidence_for_edge(self, edge: Pair, weight: float) -> float:
        """How sure the squid is about an association.

        Magnitude alone is not confidence: a synapse that keeps flipping sign
        is a guess, one that has been pushed the same way many times over many
        observations is knowledge.
        """
        events = self.weight_history(edge, limit=_MAX_EVENTS_PER_EDGE)
        magnitude = min(1.0, abs(weight) / 0.6)
        if not events:
            return round(magnitude * 0.4, 3)

        deltas = [e.delta for e in events if abs(e.delta) > 1e-6]
        if deltas:
            agreeing = sum(1 for d in deltas if (d > 0) == (weight >= 0))
            consistency = agreeing / len(deltas)
        else:
            consistency = 0.5

        samples = 0
        for e in events:
            n = e.detail.get('samples')
            if isinstance(n, (int, float)):
                samples += int(n)
        support = min(1.0, samples / 200.0) if samples else min(1.0, len(events) / 8.0)

        confidence = magnitude * (0.45 + 0.35 * consistency + 0.20 * support)
        return round(max(0.0, min(1.0, confidence)), 3)

    def _behaviour_for_edge(self, edge: Pair, weight: float) -> str:
        infl = self._influence.get(edge)
        src, dst = edge
        if infl and infl.get('ticks'):
            # Activations are centred on 50, so an excitatory synapse pushes its
            # target UP when the source is above neutral and DOWN when it is
            # below. Reporting only the net made a positive synapse read as
            # "lowering satisfaction" whenever the source had lately been quiet,
            # which flatly contradicted the statement above it.
            target = self.label(infl.get('target') or dst)
            swing = "up when" if weight > 0 else "down when"
            counter = "down" if weight > 0 else "up"
            base = (f"over {infl['ticks']} ticks it has moved {target} by "
                    f"{infl['total']:.1f} points in total "
                    f"({infl['net']:+.1f} net) - {swing} {self.label(src)} is "
                    f"above its resting level, {counter} when it is below")
            recent = self._decision_after(infl.get('last', 0.0))
            if recent:
                base += f"; the squid's next choice was to be {recent}"
            return base
        from .brain_constants import CORE_STAT_NEURONS
        if dst in CORE_STAT_NEURONS:
            return (f"when {self.label(src)} is active this nudges "
                    f"{self.label(dst)} {'up' if weight > 0 else 'down'}, which "
                    f"feeds straight into what the squid decides to do next")
        return (f"it feeds {self.label(dst)}, which in turn drives the rest of "
                f"the network")

    def _decision_after(self, timestamp: float) -> str:
        if not timestamp:
            return ""
        for ts, decision, _ in reversed(self.decisions):
            if ts >= timestamp:
                return decision
        return ""

    def _experience_for_edge(self, edge: Pair) -> Tuple[str, str, str, Optional[Episode]]:
        """Best available (experience, action, consequence, episode) for a synapse."""
        for event in reversed(self.weight_history(edge, limit=_MAX_EVENTS_PER_EDGE)):
            ep = self.get_episode(event.episode_id)
            if ep is not None:
                consequence = ", ".join(
                    f"{humanise(k)} {'rose' if d > 0 else 'fell'} by {abs(d):.0f}"
                    for k, d in sorted(ep.consequence.items(),
                                       key=lambda kv: -abs(kv[1]))[:2] if abs(d) >= 0.5)
                return (ep.describe(), ep.action, consequence, ep)

        src, dst = edge
        events = self.weight_history(edge, limit=_MAX_EVENTS_PER_EDGE)
        if events:
            n = sum(int(e.detail.get('samples') or 0) for e in events)
            when = _fmt_ago(events[0].timestamp)
            if n:
                return (f"{self.label(src)} and {self.label(dst)} were watched "
                        f"together across {n} moments of the squid's life, "
                        f"starting {when}", "", "", None)
            return (f"repeated experience starting {when}", "", "", None)
        return ("", "", "", None)

    def about_neuron(self, name: str, limit: int = 40) -> List['KnowledgeItem']:
        """Everything the squid knows that involves this neuron.

        Filtered from the same knowledge() the Knowledge tab shows, so the
        Laboratory and the Knowledge tab word the same synapse the same way.
        There is one account of what this brain knows, and both of them read it.
        """
        items = []
        for item in self.knowledge(limit=600):
            if item.neuron == name:
                items.append(item)
            elif item.edge and name in item.edge:
                items.append(item)
        return items[:limit]

    def knowledge(self, topic: Optional[str] = None, min_strength: float = 0.12,
                  limit: int = 60) -> List[KnowledgeItem]:
        """Everything the squid currently knows, in plain English.

        Reads the live weights, so this is the organism's actual knowledge and
        not a snapshot that can drift away from it.
        """
        items: List[KnowledgeItem] = []
        weights = getattr(self.brain, 'weights', {}) or {}
        # Normalise the query the same way the names are normalised. Only the
        # haystack used to have its underscores replaced, so asking about a
        # neuron by the exact name shown everywhere else in the tool -
        # "filth_avoidance" - matched nothing at all, while "filth avoidance"
        # worked. Copying a name out of the UI and pasting it into the search
        # box is the most obvious thing a reader can do with it.
        topic_l = (topic or "").strip().lower().replace('_', ' ')

        def matches(*names: str) -> bool:
            if not topic_l:
                return True
            return any(topic_l in str(n).lower().replace('_', ' ')
                       for n in names if n)

        # --- associations: the synapses themselves --------------------------
        for edge, weight in weights.items():
            if not (isinstance(edge, tuple) and len(edge) == 2):
                continue
            weight = float(weight)
            if abs(weight) < min_strength:
                continue
            src, dst = edge
            if not matches(src, dst, self.label(src), self.label(dst)):
                continue

            adverb = _strength_word(weight)
            if weight > 0:
                statement = (f"When {self.label(src)} is high, {self.label(dst)} "
                             f"{adverb} goes up.")
            else:
                statement = (f"When {self.label(src)} is high, {self.label(dst)} "
                             f"{adverb} goes down.")

            experience, action, consequence, _ep = self._experience_for_edge(edge)

            events = self.weight_history(edge, limit=4)
            if events:
                last = events[-1]
                direction = "strengthened" if last.delta > 0 else "weakened"
                reason = (f"last {direction} by {abs(last.delta):.3f} because "
                          f"{MECHANISMS.get(last.mechanism, last.mechanism)}")
                r = last.detail.get('correlation')
                if isinstance(r, (int, float)):
                    reason += f" (measured correlation {r:+.2f})"
                updated = last.timestamp
            else:
                reason = "it has not changed since the brain was built"
                updated = self._first_seen.get(edge, 0.0)

            items.append(KnowledgeItem(
                subject=self.label(dst), statement=statement,
                experience=experience, action=action, consequence=consequence,
                reason=reason,
                confidence=self._confidence_for_edge(edge, weight),
                strength=weight,
                behaviour=self._behaviour_for_edge(edge, weight),
                kind='association', edge=edge, updated=updated))

        # --- contingencies: what its own actions cause ----------------------
        causal = getattr(self.brain, 'causal_learning', None)
        if causal is not None and hasattr(causal, 'knowledge_items'):
            try:
                for item in causal.knowledge_items():
                    if matches(item.subject, item.action, item.statement):
                        items.append(item)
            except Exception:
                pass

        # --- structure: why the neurons exist -------------------------------
        for name, origin in self.origins.items():
            if not matches(name, origin.display_name, origin.deficit_summary):
                continue
            items.append(KnowledgeItem(
                subject=self.label(name),
                statement=f"It grew {origin.display_name or humanise(name)} - a neuron "
                          f"that did not exist when the squid was born.",
                experience=origin.deficit_summary,
                action="", consequence="",
                reason=DEFICIT_PHRASING.get(origin.deficit_kind, origin.deficit_kind),
                confidence=float(origin.evidence.get('confidence', 0.7) or 0.7),
                strength=sum(abs(w) for _, _, w, _ in origin.wiring) or 0.0,
                behaviour=origin.remedy or "it participates in every tick from now on",
                kind='structure', neuron=name, updated=origin.created_at))

        items.sort(key=lambda i: (-i.confidence, -abs(i.strength)))
        return items[:limit]

    def edges_touched_by(self, mechanism: str) -> Dict[Pair, float]:
        """Every synapse this mechanism has moved, and by how much in total.

        Reads the running totals rather than the narrated event list. A
        high-frequency mechanism - an outcome reaching back along the
        eligibility traces, say - moves many synapses by thousandths many times
        a minute; those changes are real and are accounted for exactly here,
        but they are not narrated one by one because four hundred lines of
        "+0.002" would bury the handful of changes that tell the squid's story.
        Anything asking "has this mechanism ever actually done anything?" has
        to ask the totals.
        """
        return {edge: totals[mechanism]
                for edge, totals in self._totals.items()
                if mechanism in totals and totals[mechanism]}

    def mechanism_totals(self) -> Dict[str, float]:
        """How far each mechanism has moved the network, summed over synapses."""
        out: Dict[str, float] = {}
        for totals in self._totals.values():
            for mechanism, delta in totals.items():
                out[mechanism] = out.get(mechanism, 0.0) + abs(delta)
        return out

    def summary(self) -> Dict[str, Any]:
        return {
            'weight_changes': self.total_changes,
            'tracked_synapses': len(self._events_by_edge),
            'neurons_grown': len(self.origins),
            'neurons_pruned': len(self.pruned),
            'episodes': len(self.episodes),
            'recent_events': len(self._recent),
            'by_mechanism': self.mechanism_totals(),
        }

    def recent_events(self, limit: int = 25) -> List[WeightEvent]:
        return list(self._recent)[-limit:]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            'version': 1,
            'total_changes': self.total_changes,
            'recent_events': [e.to_dict() for e in list(self._recent)[-200:]],
            'totals': [{'edge': list(edge), 'totals': totals,
                        'counts': self._counts.get(edge, {}),
                        'first_seen': self._first_seen.get(edge, 0.0)}
                       for edge, totals in self._totals.items()],
            'origins': {k: v.to_dict() for k, v in self.origins.items()},
            'pruned': [p.to_dict() for p in self.pruned],
            'episodes': [e.to_dict() for e in self.episodes],
            'influence': [{'edge': list(edge), **rec}
                          for edge, rec in self._influence.items()],
            'display_names': dict(self.display_names),
        }

    def from_dict(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        self._events_by_edge.clear()
        self._recent.clear()
        self._totals.clear()
        self._counts.clear()
        self._first_seen.clear()
        self.origins.clear()
        self.pruned.clear()
        self.episodes.clear()
        self._episode_index.clear()
        self._influence.clear()

        self.total_changes = int(data.get('total_changes', 0))
        self.display_names = {str(k): str(v)
                              for k, v in (data.get('display_names') or {}).items()}

        for raw in data.get('episodes') or []:
            try:
                self.record_episode(Episode.from_dict(raw))
            except Exception:
                continue

        for raw in data.get('recent_events') or []:
            event = WeightEvent.from_dict(raw) if isinstance(raw, dict) else None
            if event is None:
                continue
            bucket = self._events_by_edge.setdefault(
                event.edge, deque(maxlen=_MAX_EVENTS_PER_EDGE))
            bucket.append(event)
            self._recent.append(event)

        for raw in data.get('totals') or []:
            edge = raw.get('edge') or []
            if len(edge) != 2:
                continue
            key = (str(edge[0]), str(edge[1]))
            self._totals[key] = {str(k): float(v)
                                 for k, v in (raw.get('totals') or {}).items()}
            self._counts[key] = {str(k): int(v)
                                 for k, v in (raw.get('counts') or {}).items()}
            self._first_seen[key] = float(raw.get('first_seen', 0.0) or 0.0)

        for name, raw in (data.get('origins') or {}).items():
            try:
                self.origins[str(name)] = NeuronOrigin.from_dict(raw)
            except Exception:
                continue

        for raw in data.get('pruned') or []:
            try:
                self.pruned.append(NeuronOrigin.from_dict(raw))
            except Exception:
                continue

        for raw in data.get('influence') or []:
            edge = raw.get('edge') or []
            if len(edge) != 2:
                continue
            self._influence[(str(edge[0]), str(edge[1]))] = {
                'total': float(raw.get('total', 0.0)),
                'net': float(raw.get('net', 0.0)),
                'channel': str(raw.get('channel', 'modulation')),
                'target': str(raw.get('target', '')),
                'last': float(raw.get('last', 0.0)),
                'ticks': int(raw.get('ticks', 0)),
            }

    def reset(self) -> None:
        self.from_dict({})
