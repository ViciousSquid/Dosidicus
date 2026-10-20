# File: encounter_sensors.py
"""Where the other squid in this tank are - bookkeeping, not sense organs.

A squid sees another squid with its ordinary vision (src/vision_worker.py: a
visitor is drawn as category 'squid', and the view cone decides whether it is
seen). That, how close one is, and what it remembers of the one it is looking
at reach the brain as percepts, and touch the network only through the social
senses neurogenesis grows the first time each matters
(src.brain_constants.SOCIAL_SENSORS). No sensor neuron is registered here
(those earlier versions added are dropped from a save as it loads - see
src.brain_constants.RETIRED_NEURONS).

What is here is the tank's own record of who is present and what passed
between them - positions, contests - which encounters, memories, fights and
the fight cloud are built from. Nothing here maps "another squid" to an
action: the social neurons drive the squid's own action neurons, and the
decision engine reads the winner.
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional

from .identity import SquidIdentity

#: Beyond this a squid is a speck on the far side of the tank: visible,
#: but proximity reads zero.
PROXIMITY_RANGE = 400.0

#: Pixels per second that count as "closing fast".
FULL_CLOSING_SPEED = 60.0

#: How long a contest stays perceptible after it happens. Long enough that the
#: victim's brain gets several ticks in which the sensor is on, so it can
#: actually be an antecedent of anything.
CONTEST_LINGER = 4.0

#: A presence not refreshed for this long is gone. The network sends state at
#: about 2 Hz, so this survives a few dropped packets without a squid
#: flickering in and out of existence.
PRESENCE_TIMEOUT = 3.0

_DIRECTION_VECTORS = {
    'right': (1.0, 0.0),
    'left': (-1.0, 0.0),
    'up': (0.0, -1.0),
    'down': (0.0, 1.0),
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


class ConspecificPresence:
    """One other squid, as currently perceived."""

    __slots__ = ('identity', 'x', 'y', 'distance', 'closing_rate', 'ahead',
                 'status', 'last_update', 'contest_until', 'contest_by', 'contested_item',
                 '_last_distance', '_last_distance_at')

    def __init__(self, identity: SquidIdentity, now: float):
        self.identity = identity
        self.x = 0.0
        self.y = 0.0
        self.distance = float('inf')
        self.closing_rate = 0.0      # +ve closing, -ve receding, px/sec
        self.ahead = 0.0             # 0 behind .. 100 dead ahead
        self.status = ""
        self.last_update = now
        self.contest_until = 0.0
        self.contest_by = 'local'
        #: The object of its latest contest with this squid (a scene item),
        #: or None for a confrontation over nothing.
        self.contested_item = None
        self._last_distance: Optional[float] = None
        self._last_distance_at = now

    @property
    def uuid(self) -> str:
        return self.identity.uuid

    def is_contesting(self, now: float) -> bool:
        return now < self.contest_until


class ConspecificView:
    """What other squid are doing, from this squid's point of view.

    Published on TamagotchiLogic as `conspecific_view`, the same way
    `latest_vision_result` is, so the engine can consult it through getattr
    and run perfectly well without it.
    """

    def __init__(self, clock=time.time):
        self.clock = clock
        self.presences: Dict[str, ConspecificPresence] = {}
        self._contest_log: List[Dict[str, Any]] = []
        #: Told the rival's uuid the moment a contest happens, on the thread
        #: that resolved it. Used to draw the scuffle; it decides nothing.
        self.on_contest: Optional[Callable[[str], None]] = None

    # -- feeding it -----------------------------------------------------
    def observe_peer(self, identity: SquidIdentity, x: float, y: float,
                     observer_x: float, observer_y: float,
                     facing: str = 'right', status: str = "",
                     now: Optional[float] = None) -> ConspecificPresence:
        """Record where one other squid is, relative to this one."""
        stamp = now if now is not None else self.clock()
        presence = self.presences.get(identity.uuid)
        if presence is None:
            presence = ConspecificPresence(identity, stamp)
            self.presences[identity.uuid] = presence
        else:
            presence.identity = identity

        dx = float(x) - float(observer_x)
        dy = float(y) - float(observer_y)
        distance = math.hypot(dx, dy)

        # Closing rate, from the change in distance since we last looked.
        elapsed = stamp - presence._last_distance_at
        if presence._last_distance is not None and elapsed > 1e-3:
            presence.closing_rate = (presence._last_distance - distance) / elapsed
        presence._last_distance = distance
        presence._last_distance_at = stamp

        presence.x = float(x)
        presence.y = float(y)
        presence.distance = distance
        presence.status = str(status or "")
        presence.last_update = stamp
        presence.ahead = self._ahead_score(dx, dy, facing)
        return presence

    @staticmethod
    def _ahead_score(dx: float, dy: float, facing: str) -> float:
        """How squarely the other squid sits in front of this one.

        100 is dead ahead and 0 is directly behind. Encoded this way round
        because a sensor at rest must mean "nothing to report", and something
        behind the squid is exactly that - it cannot see it.
        """
        vector = _DIRECTION_VECTORS.get(str(facing).lower())
        length = math.hypot(dx, dy)
        if vector is None or length < 1e-6:
            return 0.0
        cosine = (dx * vector[0] + dy * vector[1]) / length
        return _clamp((cosine + 1.0) * 50.0)

    def forget_peer(self, peer_uuid: str) -> None:
        self.presences.pop(str(peer_uuid), None)

    def clear(self) -> None:
        self.presences.clear()

    def prune(self, now: Optional[float] = None) -> None:
        """Drop anything we have stopped hearing about."""
        stamp = now if now is not None else self.clock()
        stale = [uuid for uuid, p in self.presences.items()
                 if stamp - p.last_update > PRESENCE_TIMEOUT]
        for uuid in stale:
            del self.presences[uuid]

    # -- reading it -----------------------------------------------------
    def nearest(self, now: Optional[float] = None, bounds=None) -> Optional[ConspecificPresence]:
        """The other squid this one would be reacting to, if any."""
        stamp = now if now is not None else self.clock()
        live = [p for p in self.presences.values()
                if stamp - p.last_update <= PRESENCE_TIMEOUT]
        if bounds is not None:
            width, height = bounds
            live = [p for p in live if 0 <= p.x <= width and 0 <= p.y <= height]
        if not live:
            return None
        return min(live, key=lambda p: p.distance)

    def any_contesting(self, now: Optional[float] = None) -> bool:
        stamp = now if now is not None else self.clock()
        return any(p.is_contesting(stamp) for p in self.presences.values())

    # -- consequences ---------------------------------------------------
    def note_contest(self, rival, item=None, taken: bool = False,
                     squid=None, now: Optional[float] = None,
                     by: str = 'local') -> None:
        """A contest happened with this squid. Called by the actuator.

        Recorded rather than scored: what it did to either squid is measured
        from their drives when the encounter closes, not decided here.

        `by` says WHICH squid ended up with the object - 'local' when this
        squid took it, 'peer' when the other one did. Without it the same
        record meant opposite things depending on who wrote it, and a squid
        that had just been robbed filed the event as a gain.
        """
        stamp = now if now is not None else self.clock()
        presence = self.presences.get(getattr(rival, 'uuid', ''))
        if presence is not None:
            presence.contest_until = stamp + CONTEST_LINGER
            presence.contest_by = 'peer' if by == 'peer' else 'local'
            presence.contested_item = item
        self._contest_log.append({
            'peer_uuid': getattr(rival, 'uuid', ''),
            'taken': bool(taken),
            'by': 'peer' if by == 'peer' else 'local',
            'at': stamp,
            'item': getattr(item, 'filename', None),
        })
        if len(self._contest_log) > 50:
            del self._contest_log[:-50]
        listener = self.on_contest
        if listener is not None:
            try:
                listener(getattr(rival, 'uuid', ''))
            except Exception:
                pass

    def drain_contests(self) -> List[Dict[str, Any]]:
        """Contests since the last call, for the encounter session to file."""
        log, self._contest_log = self._contest_log, []
        return log


__all__ = ['ConspecificView', 'ConspecificPresence', 'PROXIMITY_RANGE', 'FULL_CLOSING_SPEED', 'CONTEST_LINGER',
           'PRESENCE_TIMEOUT']
