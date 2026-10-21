# File: remote_protocol.py
"""The four messages a visiting squid and its host tank exchange.

The visiting squid's brain stays at home. Its body is on the host. So the
round trip is:

    host tank                                    visitor's home instance
    ---------                                    -----------------------
    what the visitor can see  --perception_frame->  its own sensors
                                                    its own propagation
                                                    its own action neurons
    apply it, resolve it      <--action_intent----   its own decision
    what actually happened    --consequence------->  its own senses again

This module is only the envelope. It is deliberately NOT a generic RPC layer:
there are four message types, each with a fixed shape, and everything is
validated on arrival because all of it comes from another machine.

TWO RULES DECIDE WHAT MAY BE IN A MESSAGE
-----------------------------------------
1. Only what the other squid could actually observe. A resident squid can see
   where a visitor is and what it is doing. It cannot see how hungry the
   visitor is, what the visitor remembers, or what the visitor is about to do,
   so none of that crosses.

2. Private cognitive state never leaves home. Weights, neuron activations,
   drives, memories, the capability ledger - a host tank has no use for any of
   it, and a host that had it could simulate the visitor, which is the one
   thing this whole design exists to prevent.

An ACTION INTENT IS A LEASE, NOT A COMMAND
------------------------------------------
Every intent expires. If the network drops after the visitor asks to swim
left, the host stops applying it when the lease runs out and the visitor comes
to a stop. A command without an expiry would leave a visitor swimming into a
wall forever because a packet went missing.
"""

import time
from typing import Any, Dict, Optional, Tuple

from .identity import SquidIdentity, ENCOUNTER_PROTOCOL_VERSION

# --- message types -----------------------------------------------------
MSG_PERCEPTION_FRAME = 'perception_frame'
MSG_ACTION_INTENT = 'action_intent'
MSG_CONSEQUENCE = 'consequence'
MSG_VISIT_END = 'visit_end'
#: Visitor -> host, after a mating: half of its weights, for the egg.
MSG_GAMETE = 'gamete'

REMOTE_MIND_MESSAGES = (MSG_PERCEPTION_FRAME, MSG_ACTION_INTENT,
                        MSG_CONSEQUENCE, MSG_VISIT_END, MSG_GAMETE)

#: The behavioural cadence, in seconds. Both endpoints run on it: the host
#: sends a frame this often and the visitor answers with an intent.
ROUND_TRIP_INTERVAL = 0.5

#: How long an intent stays valid. Two cadences plus a margin, so one dropped
#: packet does not stall the visitor but four seconds of silence does stop it.
INTENT_LEASE = 1.5

#: No frame for this long and the visitor concludes the host is gone and comes
#: home. No intent for this long and the host stops moving the visitor.
LINK_TIMEOUT = 4.0

#: ...and this long, and the host ends the visit outright.
VISIT_ABANDON_TIMEOUT = 12.0

#: The values a HOST is allowed to compute for a visitor. Everything here is
#: something the host can see from its own tank.
#:
#: The first three feed the visitor's own built-in sensors. The rest are
#: percepts, not neurons, which reach the visitor's network only through the
#: social senses it grows (src.brain_constants.SOCIAL_SENSORS): squid_in_view
#: is its vision of the resident, by the same view cone its own vision uses
#: (src.vision_cone); squid_proximity how close the resident is; in_fight that
#: its body is in a scuffle.
#:
#: Nothing here is the visitor's memory of the resident: that stays at home,
#: and a host cannot know it.
OBSERVABLE_SENSORS = (
    'can_see_food',
    'plant_proximity',
    'external_stimulus',
    'squid_in_view',
    'squid_proximity',
    'in_fight',
)

#: Keys that would carry private cognitive state. A message containing any of
#: them is rejected outright rather than filtered, because its presence means
#: the sender is not speaking this protocol.
FORBIDDEN_KEYS = frozenset({
    'weights', 'state', 'brain', 'brain_state', 'neurons', 'neuron_positions',
    'memory', 'memories', 'short_term_memory', 'long_term_memory',
    'neurogenesis', 'capability', 'plasticity', 'provenance', 'causal_learning',
    'hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity',
    'cleanliness', 'sleepiness', 'personality_bias', 'peer_ledger',
})

HEADINGS = ('left', 'right', 'up', 'down')

#: Consequence kinds. Each names something that HAPPENED, never how the
#: visitor should feel about it - the visitor's own brain decides that, from
#: what the consequence does to its senses and drives.
CONSEQUENCE_CONTEST = 'contest_resolved'
CONSEQUENCE_ATE = 'ate'
CONSEQUENCE_BLOCKED = 'blocked'
CONSEQUENCE_EJECTED = 'ejected'
#: The two bodies' contact during this visit was a mating, and the egg is in
#: the host's tank. The host decided it and has already recorded it; this only
#: tells the visitor, carrying the mating id and nothing else, so the visitor
#: can remember it once however many times it is told.
CONSEQUENCE_MATED = 'mated'
CONSEQUENCE_FIGHT = 'fight_resolved'
#: A thrown rock struck the visitor. Only that, and how hard - never why: the
#: thrower might have been playing or attacking, and the struck squid's own
#: brain makes of it what it will.
CONSEQUENCE_HIT = 'hit'
CONSEQUENCE_THROWN = 'rock_thrown'

CONSEQUENCE_KINDS = (CONSEQUENCE_CONTEST, CONSEQUENCE_ATE,
                     CONSEQUENCE_BLOCKED, CONSEQUENCE_EJECTED,
                     CONSEQUENCE_MATED, CONSEQUENCE_FIGHT, CONSEQUENCE_HIT,
                     CONSEQUENCE_THROWN)

_MAX_ITEM_ID = 40
_MAX_ITEMS_IN_FRAME = 8


class ProtocolError(ValueError):
    """A message that cannot be trusted. Always caught at the boundary."""


# --- helpers -----------------------------------------------------------
def _clamp(value: Any, low: float, high: float, default: float = 0.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def _reject_private(payload: Dict[str, Any]) -> None:
    """Refuse anything carrying private cognitive state, at any depth."""
    stack = [payload]
    seen = 0
    while stack:
        current = stack.pop()
        seen += 1
        if seen > 200:          # a payload this deep is not one of ours
            raise ProtocolError("payload nested too deeply")
        if isinstance(current, dict):
            for key, value in current.items():
                if str(key).lower() in FORBIDDEN_KEYS:
                    raise ProtocolError(
                        f"'{key}' is private cognitive state and must not cross")
                stack.append(value)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)


def _clean_item_id(value: Any) -> Optional[str]:
    """An item reference is an opaque id the HOST issued, never a path.

    The visitor can only ever name something the host told it about, so no
    filename, scene handle or path is expressible in this protocol at all.
    """
    if not isinstance(value, str):
        return None
    cleaned = value.strip()[:_MAX_ITEM_ID]
    if not cleaned or not cleaned.replace('-', '').replace('_', '').isalnum():
        return None
    return cleaned


# ======================================================================
# Host -> visitor: what the visiting squid can see
# ======================================================================
class PerceptionFrame:
    """One tick of the host tank, as the visiting squid perceives it."""

    __slots__ = ('visit_id', 'seq', 'sent_at', 'x', 'y', 'tank_width',
                 'tank_height', 'facing', 'sensors', 'resident', 'items')

    def __init__(self, visit_id: str, seq: int = 0, sent_at: float = 0.0):
        self.visit_id = visit_id
        self.seq = int(seq)
        self.sent_at = float(sent_at or time.time())
        self.x = 0.0
        self.y = 0.0
        self.tank_width = 1280.0
        self.tank_height = 900.0
        self.facing = 'right'
        self.sensors: Dict[str, float] = {}
        self.resident: Optional[SquidIdentity] = None
        self.items: list = []      # [{'id': str, 'dx': float, 'dy': float}]

    def to_payload(self) -> Dict[str, Any]:
        return {
            'visit_id': self.visit_id,
            'seq': self.seq,
            'sent_at': self.sent_at,
            'x': round(self.x, 2),
            'y': round(self.y, 2),
            'tank': [self.tank_width, self.tank_height],
            'facing': self.facing,
            # Only the observable ones, filtered here as well as checked on
            # arrival, so a host bug cannot leak a sensor it should not send.
            'sensors': {name: round(float(value), 2)
                        for name, value in self.sensors.items()
                        if name in OBSERVABLE_SENSORS},
            'resident': self.resident.to_payload() if self.resident else None,
            'items': self.items[:_MAX_ITEMS_IN_FRAME],
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> 'PerceptionFrame':
        if not isinstance(payload, dict):
            raise ProtocolError("perception frame must be a dictionary")
        _reject_private(payload)

        visit_id = payload.get('visit_id')
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise ProtocolError("perception frame has no visit id")

        frame = cls(visit_id.strip()[:64],
                    seq=_clamp(payload.get('seq', 0), 0, 1e12),
                    sent_at=_clamp(payload.get('sent_at', 0.0), 0, 1e12))
        frame.x = _clamp(payload.get('x'), -1e5, 1e5)
        frame.y = _clamp(payload.get('y'), -1e5, 1e5)

        tank = payload.get('tank') or []
        if isinstance(tank, (list, tuple)) and len(tank) == 2:
            frame.tank_width = _clamp(tank[0], 1.0, 1e5, 1280.0)
            frame.tank_height = _clamp(tank[1], 1.0, 1e5, 900.0)

        facing = payload.get('facing')
        frame.facing = facing if facing in HEADINGS else 'right'

        sensors = payload.get('sensors')
        if not isinstance(sensors, dict):
            raise ProtocolError("perception frame has no sensors")
        frame.sensors = {name: _clamp(value, 0.0, 100.0)
                         for name, value in sensors.items()
                         if name in OBSERVABLE_SENSORS}

        frame.resident = SquidIdentity.from_payload(payload.get('resident') or {})

        items = payload.get('items')
        if isinstance(items, (list, tuple)):
            for entry in items[:_MAX_ITEMS_IN_FRAME]:
                if not isinstance(entry, dict):
                    continue
                item_id = _clean_item_id(entry.get('id'))
                if item_id is None:
                    continue
                frame.items.append({
                    'id': item_id,
                    'dx': _clamp(entry.get('dx'), -1e5, 1e5),
                    'dy': _clamp(entry.get('dy'), -1e5, 1e5),
                    'contested': bool(entry.get('contested', False)),
                })
        return frame

    def nearest_item(self, contested_only: bool = False) -> Optional[Dict[str, Any]]:
        candidates = [i for i in self.items
                      if not contested_only or i.get('contested')]
        if not candidates:
            return None
        return min(candidates, key=lambda i: (i['dx'] ** 2 + i['dy'] ** 2))


# ======================================================================
# Visitor -> host: what the visiting squid's brain decided
# ======================================================================
class ActionIntent:
    """One decision by the visitor's own brain, as a lease on its body.

    `action` is an action NEURON name, which is the whole vocabulary: the host
    can only ever be asked for something the squid's network could have wanted.
    There is no free-form command.
    """

    __slots__ = ('visit_id', 'seq', 'sent_at', 'action', 'activation',
                 'confidence', 'heading', 'target_id', 'lease',
                 'aggression', 'defence', 'fitness', 'practice')

    def __init__(self, visit_id: str, action: str, seq: int = 0,
                 sent_at: float = 0.0, activation: float = 0.0,
                 confidence: float = 0.0, heading: str = '',
                 target_id: str = '', lease: float = INTENT_LEASE,
                 aggression: float = 0.0, defence: float = 0.0,
                 fitness: float = 1.0, practice: int = 0):
        self.visit_id = visit_id
        self.seq = int(seq)
        self.sent_at = float(sent_at or time.time())
        self.action = action
        self.activation = float(activation)
        self.confidence = float(confidence)
        self.heading = heading
        self.target_id = target_id
        self.lease = float(lease)
        # How this squid would fight, worked out at home from its own brain
        # and body (src/fighting.py): its aggression neuron, how hard it
        # would fight back, and its fitness. What it shows in a fight, not
        # what is in its brain - the host needs them only to resolve one.
        self.aggression = float(aggression)
        self.defence = float(defence)
        self.fitness = float(fitness)
        # How practised a thrower it is (throws made, from its own record at
        # home): how far its throws stray in the host's tank (src/throwing.py).
        self.practice = int(practice)

    @property
    def expires_at(self) -> float:
        return self.sent_at + self.lease

    def is_live(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) < self.expires_at

    def to_payload(self) -> Dict[str, Any]:
        return {
            'visit_id': self.visit_id,
            'seq': self.seq,
            'sent_at': self.sent_at,
            'action': self.action,
            'activation': round(self.activation, 2),
            'confidence': round(self.confidence, 3),
            'heading': self.heading,
            'target_id': self.target_id,
            'lease': self.lease,
            'aggression': round(self.aggression, 1),
            'defence': round(self.defence, 1),
            'fitness': round(self.fitness, 3),
            'practice': self.practice,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any],
                     allowed_actions=None) -> 'ActionIntent':
        if not isinstance(payload, dict):
            raise ProtocolError("action intent must be a dictionary")
        _reject_private(payload)

        visit_id = payload.get('visit_id')
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise ProtocolError("action intent has no visit id")

        action = payload.get('action')
        if allowed_actions is None:
            from src.brain_constants import ACTION_NEURONS
            allowed_actions = set(ACTION_NEURONS)
        if action not in allowed_actions:
            raise ProtocolError(f"'{action}' is not an action neuron")

        heading = payload.get('heading')
        target = _clean_item_id(payload.get('target_id'))
        return cls(
            visit_id=visit_id.strip()[:64],
            action=action,
            seq=int(_clamp(payload.get('seq', 0), 0, 1e12)),
            sent_at=_clamp(payload.get('sent_at', 0.0), 0, 1e12),
            activation=_clamp(payload.get('activation'), 0.0, 100.0),
            confidence=_clamp(payload.get('confidence'), 0.0, 1.0),
            heading=heading if heading in HEADINGS else '',
            target_id=target or '',
            # A visitor cannot grant itself an indefinite lease on its own
            # body: the host caps it at the protocol's value.
            lease=_clamp(payload.get('lease', INTENT_LEASE), 0.0, INTENT_LEASE,
                         INTENT_LEASE),
            aggression=_clamp(payload.get('aggression', 0.0), 0.0, 100.0, 0.0),
            defence=_clamp(payload.get('defence', 0.0), 0.0, 100.0, 0.0),
            # An honest squid at its best is about 2; nothing claims more than 3.
            fitness=_clamp(payload.get('fitness', 1.0), 0.0, 3.0, 1.0),
            practice=int(_clamp(payload.get('practice', 0), 0, 100000, 0)),
        )


# ======================================================================
# Visitor -> host, after a mating: half of its weights
# ======================================================================
class Gamete:
    """Half of the visiting squid's weights, for the egg the host is keeping.

    The one time any of a squid's weights leave its own machine, and only
    this: after the host has told it of a mating, a random half of its
    synapses between the neurons every newborn has (src/inheritance.py) -
    no grown neuron, no state, no memory. Reduced on arrival to exactly
    that; the host keeps it only for its own egg from that mating.
    """

    __slots__ = ('visit_id', 'mating_id', 'genes')

    def __init__(self, visit_id: str, mating_id: str, genes: Dict[str, float]):
        self.visit_id = visit_id
        self.mating_id = mating_id
        self.genes = dict(genes or {})

    def to_payload(self) -> Dict[str, Any]:
        return {'visit_id': self.visit_id, 'mating_id': self.mating_id,
                'genes': dict(self.genes)}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> 'Gamete':
        from src.inheritance import clean_gamete
        from src.lifecycle import is_valid_mating_id
        if not isinstance(payload, dict):
            raise ProtocolError("gamete must be a dictionary")
        if set(payload) - {'visit_id', 'mating_id', 'genes'}:
            raise ProtocolError("gamete carries something other than genes")
        visit_id = payload.get('visit_id')
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise ProtocolError("gamete has no visit id")
        mating_id = payload.get('mating_id')
        if not is_valid_mating_id(mating_id):
            raise ProtocolError("gamete names no valid mating")
        genes = clean_gamete(payload.get('genes'))
        if not genes:
            raise ProtocolError("gamete carries no genes")
        return cls(visit_id.strip()[:64], mating_id, genes)


# ======================================================================
# Host -> visitor: what actually happened
# ======================================================================
class Consequence:
    """An observable result of something the visitor did.

    Descriptive only. "You now carry the object" and "you did not get it" are
    facts; whether that was good is for the visitor's drives to register and
    its own network to learn from.
    """

    __slots__ = ('visit_id', 'kind', 'at', 'detail')

    def __init__(self, visit_id: str, kind: str, at: float = 0.0,
                 detail: Optional[Dict[str, Any]] = None):
        self.visit_id = visit_id
        self.kind = kind
        self.at = float(at or time.time())
        self.detail = dict(detail or {})

    def to_payload(self) -> Dict[str, Any]:
        return {'visit_id': self.visit_id, 'kind': self.kind,
                'at': self.at, 'detail': self.detail}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> 'Consequence':
        if not isinstance(payload, dict):
            raise ProtocolError("consequence must be a dictionary")
        _reject_private(payload)
        visit_id = payload.get('visit_id')
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise ProtocolError("consequence has no visit id")
        kind = payload.get('kind')
        if kind not in CONSEQUENCE_KINDS:
            raise ProtocolError(f"unknown consequence kind: {kind}")
        detail = payload.get('detail')
        if not isinstance(detail, dict):
            detail = {}
        clean: Dict[str, Any] = {}
        for key, value in list(detail.items())[:12]:
            key = str(key)[:32]
            if isinstance(value, bool):
                clean[key] = value
            elif isinstance(value, (int, float)):
                clean[key] = _clamp(value, -1e6, 1e6)
            elif isinstance(value, str):
                clean[key] = value[:64]
        return cls(visit_id.strip()[:64], kind,
                   at=_clamp(payload.get('at', 0.0), 0, 1e12), detail=clean)


# ======================================================================
# Either direction: the visit is over
# ======================================================================
END_DEPARTED = 'departed'         # the visitor chose to leave
END_EJECTED = 'ejected'           # the host ended it
END_LINK_LOST = 'link_lost'       # neither side chose it
END_REASONS = (END_DEPARTED, END_EJECTED, END_LINK_LOST)


class VisitEnd:
    __slots__ = ('visit_id', 'reason')

    def __init__(self, visit_id: str, reason: str = END_DEPARTED):
        self.visit_id = visit_id
        self.reason = reason if reason in END_REASONS else END_DEPARTED

    def to_payload(self) -> Dict[str, Any]:
        return {'visit_id': self.visit_id, 'reason': self.reason}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> 'VisitEnd':
        if not isinstance(payload, dict):
            raise ProtocolError("visit end must be a dictionary")
        visit_id = payload.get('visit_id')
        if not isinstance(visit_id, str) or not visit_id.strip():
            raise ProtocolError("visit end has no visit id")
        return cls(visit_id.strip()[:64], str(payload.get('reason', '')))


def new_visit_id(local_uuid: str, peer_uuid: str, now: Optional[float] = None) -> str:
    """A name for one visit, so a stale packet from the last one is ignored."""
    stamp = int((now if now is not None else time.time()) * 1000)
    return f"{str(local_uuid)[:8]}-{str(peer_uuid)[:8]}-{stamp:x}"


def mating_id_for(visit_id: str) -> str:
    """The name of the one mating a visit can produce.

    Derived from the visit, which the host named, so the same event always has
    the same id however often it is reported, and a visit can never produce
    two.
    """
    return f"{str(visit_id)[:58]}-mate"


__all__ = [
    'PerceptionFrame', 'ActionIntent', 'Consequence', 'VisitEnd',
    'ProtocolError', 'new_visit_id',
    'MSG_PERCEPTION_FRAME', 'MSG_ACTION_INTENT', 'MSG_CONSEQUENCE',
    'MSG_VISIT_END', 'MSG_GAMETE', 'Gamete', 'REMOTE_MIND_MESSAGES',
    'ROUND_TRIP_INTERVAL', 'INTENT_LEASE', 'LINK_TIMEOUT',
    'VISIT_ABANDON_TIMEOUT',
    'OBSERVABLE_SENSORS', 'FORBIDDEN_KEYS', 'HEADINGS',
    'CONSEQUENCE_CONTEST', 'CONSEQUENCE_ATE', 'CONSEQUENCE_BLOCKED',
    'CONSEQUENCE_EJECTED', 'CONSEQUENCE_MATED', 'CONSEQUENCE_FIGHT', 'CONSEQUENCE_HIT',
    'CONSEQUENCE_THROWN',
    'CONSEQUENCE_KINDS',
    'mating_id_for',
    'END_DEPARTED', 'END_EJECTED', 'END_LINK_LOST', 'END_REASONS',
    'ENCOUNTER_PROTOCOL_VERSION',
]
