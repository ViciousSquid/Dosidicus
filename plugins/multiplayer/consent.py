# File: consent.py
"""Whether a visiting squid is allowed in.

Entry used to be unconditional: a `squid_exit` message from anywhere on the
multicast group created a visitor in the tank. This is the smallest thing that
turns that into a decision the host makes - a request, an answer, and a rule
that an unanswered request is not an entry.

Deliberately not here: matchmaking, lobbies, accounts, invitations, NAT
traversal. LAN, and one host saying yes or no.
"""

import time
from typing import Any, Dict, Optional, Set

#: Every visitor is admitted. Convenient on a trusted LAN, and the setting a
#: pair of instances on one machine will normally run in.
MODE_OPEN = 'open'
#: Only peers on the allow list are admitted; everyone else is refused.
MODE_KNOWN = 'known'
#: Nobody is admitted.
MODE_CLOSED = 'closed'

MODES = (MODE_OPEN, MODE_KNOWN, MODE_CLOSED)

#: A decision is remembered this long, so a visitor that is bounced does not
#: immediately ask again on the next sync tick.
DECISION_TTL = 30.0

REASON_ACCEPTED = 'accepted'
REASON_CLOSED = 'tank_closed'
REASON_UNKNOWN_PEER = 'not_on_allow_list'
REASON_DENIED = 'denied'
REASON_AT_CAPACITY = 'tank_full'
REASON_BAD_IDENTITY = 'unusable_identity'
REASON_INCOMPATIBLE = 'protocol_mismatch'


class ConsentDecision:
    """The answer to one entry request."""

    __slots__ = ('accepted', 'reason', 'peer_uuid', 'at')

    def __init__(self, accepted: bool, reason: str, peer_uuid: str = "",
                 at: float = 0.0):
        self.accepted = bool(accepted)
        self.reason = reason
        self.peer_uuid = peer_uuid
        self.at = at or time.time()

    def to_payload(self) -> Dict[str, Any]:
        return {'accepted': self.accepted, 'reason': self.reason,
                'peer_uuid': self.peer_uuid}

    def __bool__(self) -> bool:
        return self.accepted

    def __repr__(self) -> str:
        verdict = 'accept' if self.accepted else 'refuse'
        return f"<ConsentDecision {verdict} {self.peer_uuid[:8]} ({self.reason})>"


class ConsentPolicy:
    """The host's rule about who may enter its tank."""

    def __init__(self, mode: str = MODE_OPEN, max_visitors: int = 3,
                 clock=time.time):
        self.mode = mode if mode in MODES else MODE_OPEN
        self.max_visitors = max(0, int(max_visitors))
        self.clock = clock
        self.allowed: Set[str] = set()
        self.blocked: Set[str] = set()
        self._decisions: Dict[str, ConsentDecision] = {}

    # -- configuring ----------------------------------------------------
    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown consent mode: {mode}")
        self.mode = mode

    def allow(self, peer_uuid: str) -> None:
        peer_uuid = str(peer_uuid)
        self.allowed.add(peer_uuid)
        self.blocked.discard(peer_uuid)
        self._decisions.pop(peer_uuid, None)

    def block(self, peer_uuid: str) -> None:
        peer_uuid = str(peer_uuid)
        self.blocked.add(peer_uuid)
        self.allowed.discard(peer_uuid)
        self._decisions.pop(peer_uuid, None)

    # -- deciding -------------------------------------------------------
    def evaluate(self, identity, current_visitors: int = 0) -> ConsentDecision:
        """Decide whether this visitor may enter. Never raises."""
        now = self.clock()
        if identity is None or not getattr(identity, 'uuid', ''):
            return ConsentDecision(False, REASON_BAD_IDENTITY, "", now)
        peer_uuid = identity.uuid

        if hasattr(identity, 'is_compatible') and not identity.is_compatible():
            return self._remember(ConsentDecision(
                False, REASON_INCOMPATIBLE, peer_uuid, now))
        if peer_uuid in self.blocked:
            return self._remember(ConsentDecision(False, REASON_DENIED,
                                                  peer_uuid, now))
        if self.mode == MODE_CLOSED:
            return self._remember(ConsentDecision(False, REASON_CLOSED,
                                                  peer_uuid, now))
        if self.mode == MODE_KNOWN and peer_uuid not in self.allowed:
            return self._remember(ConsentDecision(False, REASON_UNKNOWN_PEER,
                                                  peer_uuid, now))
        if self.max_visitors and current_visitors >= self.max_visitors:
            return self._remember(ConsentDecision(False, REASON_AT_CAPACITY,
                                                  peer_uuid, now))
        return self._remember(ConsentDecision(True, REASON_ACCEPTED,
                                              peer_uuid, now))

    def is_admitted(self, peer_uuid: str) -> bool:
        """Has this peer been granted entry, and is that grant still current?

        Entry is checked against a decision that was actually made. A visitor
        whose request was never answered is not admitted, which is the
        difference between asking and arriving.
        """
        decision = self._decisions.get(str(peer_uuid))
        if decision is None:
            return False
        if self.clock() - decision.at > DECISION_TTL:
            return False
        return decision.accepted

    def last_decision(self, peer_uuid: str) -> Optional[ConsentDecision]:
        return self._decisions.get(str(peer_uuid))

    def forget(self, peer_uuid: str) -> None:
        self._decisions.pop(str(peer_uuid), None)

    def _remember(self, decision: ConsentDecision) -> ConsentDecision:
        self._decisions[decision.peer_uuid] = decision
        return decision


__all__ = ['ConsentPolicy', 'ConsentDecision', 'MODE_OPEN', 'MODE_KNOWN',
           'MODE_CLOSED', 'MODES', 'DECISION_TTL',
           'REASON_ACCEPTED', 'REASON_CLOSED', 'REASON_UNKNOWN_PEER',
           'REASON_DENIED', 'REASON_AT_CAPACITY', 'REASON_BAD_IDENTITY',
           'REASON_INCOMPATIBLE']
