# File: encounter.py
"""An encounter, as a thing with a beginning, a middle and an outcome.

The unit here is the ENCOUNTER, not the tick. A tick is what the sensors
report; an encounter is the bout the squid will remember, and it is the bout
that has an outcome worth attributing anything to.

What this module deliberately does NOT do:

  * it does not choose an action. The action neurons compete and the decision
    engine reads the winner; this only records what the squid did.
  * it does not score a joint outcome from a table of move pairs. The outcome
    is measured from what actually happened to the squid's drives while the
    encounter was open, which is the same evidence causal_learning uses.
  * it does not decide that anything should be learned or grown. It produces
    the record; the existing capability monitor decides, later and on its own
    evidence, whether the network turned out to be unable to represent it.
"""

import time
from typing import Any, Dict, List, Optional

from .identity import SquidIdentity

#: Drives whose movement during an encounter is what "how did that go" means.
#: Signed: a positive weight means "more of this was good for the squid".
OUTCOME_DRIVES = {
    'happiness':    1.0,
    'satisfaction': 1.0,
    'curiosity':    0.25,
    'anxiety':     -1.0,
}

#: An encounter closes once the other squid has been out of sight this long.
#: Short enough that looking away does not merge two meetings into one; long
#: enough that a squid circling in and out of its own view cone does not
#: produce a dozen encounters with the same individual in a minute.
LOST_SIGHT_GRACE = 6.0

#: Encounters cannot run forever. A visitor that parks itself in the tank is
#: still one encounter, but it gets written down periodically rather than only
#: when it eventually leaves.
MAX_ENCOUNTER_DURATION = 180.0

#: Below this, nothing memorable happened and no memory is written. Seeing
#: another squid across the tank for two seconds is not an experience.
MIN_ENCOUNTER_DURATION = 2.0

#: Importance is what decides whether MemoryManager promotes a memory to
#: long-term storage (>= 7). An encounter that moved the squid's drives
#: sharply should survive the session; a quiet one need not.
_BASE_IMPORTANCE = 3.0
_IMPORTANCE_PER_VALENCE = 0.22
_MAX_IMPORTANCE = 10.0


#: The drives an encounter's outcome is measured against. One definition,
#: because the visiting squid and the resident squid measure the same visit
#: from their own ends and a disagreement about which drives count would make
#: the two records incomparable.
SNAPSHOT_DRIVES = ('hunger', 'happiness', 'satisfaction', 'anxiety',
                   'curiosity', 'cleanliness', 'sleepiness')


def drive_snapshot(squid) -> Dict[str, float]:
    """Where a squid's drives stand right now."""
    if squid is None:
        return {}
    snapshot = {}
    for drive in SNAPSHOT_DRIVES:
        value = getattr(squid, drive, None)
        if isinstance(value, (int, float)):
            snapshot[drive] = float(value)
    return snapshot


class EncounterRecord:
    """The finished experience: what happened, and how it went."""

    __slots__ = ('peer', 'started_at', 'ended_at', 'actions', 'peer_actions',
                 'drive_deltas', 'valence', 'outcome', 'items_taken',
                 'items_lost', 'closest_approach', 'first_meeting',
                 'related_neurons')

    def __init__(self, peer: SquidIdentity, started_at: float):
        self.peer = peer
        self.started_at = started_at
        self.ended_at = 0.0
        self.actions: List[str] = []          # what this squid did
        self.peer_actions: List[str] = []     # what the other squid was seen doing
        self.drive_deltas: Dict[str, float] = {}
        self.valence = 0.0
        self.outcome = "quiet"
        self.items_taken = 0
        self.items_lost = 0
        self.closest_approach = 0.0
        self.first_meeting = True
        self.related_neurons: List[str] = []

    @property
    def duration(self) -> float:
        return max(0.0, (self.ended_at or time.time()) - self.started_at)

    @property
    def memory_key(self) -> str:
        return self.peer.memory_key

    @property
    def importance(self) -> float:
        """How much this deserves to be remembered.

        Deliberately a function of how far the encounter moved the squid,
        not of what kind of encounter someone decided it was. A theft and a
        fright both register because both moved something.
        """
        weight = _BASE_IMPORTANCE + abs(self.valence) * _IMPORTANCE_PER_VALENCE
        if self.items_taken or self.items_lost:
            weight += 2.0
        if self.first_meeting:
            weight += 1.0
        return round(min(_MAX_IMPORTANCE, weight), 2)

    def to_memory_value(self) -> Dict[str, Any]:
        """The memory's payload.

        `valence` is deliberately the ONLY number at the top level, and every
        other figure is nested under 'detail'. MemoryManager.format_memory()
        colours a memory by summing the numeric values of its dict, so any
        number sitting beside valence would be added into that verdict:
        a raw anxiety delta of +30 would read as a good outcome, and a
        duration of 12 seconds would read as twelve points of happiness.

        Note that a bool is an int in Python, so flags are nested too.
        """
        return {
            'valence': round(self.valence, 2),
            'peer_uuid': self.peer.uuid,
            'peer_name': self.peer.name,
            'peer_personality': self.peer.personality,
            'outcome': self.outcome,
            'detail': {
                'drive_deltas': dict(self.drive_deltas),
                'duration': round(self.duration, 1),
                'my_actions': list(self.actions),
                'their_actions': list(self.peer_actions),
                'items_taken': self.items_taken,
                'items_lost': self.items_lost,
                'closest_approach': round(self.closest_approach, 1),
                'first_meeting': self.first_meeting,
                'encounters': 1,
            },
        }

    def describe(self) -> str:
        who = self.peer.name or self.peer.short_id
        return (f"{self.outcome} encounter with {who} "
                f"({self.duration:.0f}s, valence {self.valence:+.1f})")


class EncounterSession:
    """One open encounter with one individual.

    Fed a drive snapshot and the squid's current action on every tick; asked
    whether it should close; produces one EncounterRecord when it does.
    """

    def __init__(self, peer: SquidIdentity, drives: Dict[str, float],
                 first_meeting: bool = True, now: Optional[float] = None,
                 clock=time.time):
        self.clock = clock
        self.peer = peer
        self.started_at = now if now is not None else clock()
        self.opening_drives = dict(drives or {})
        self.first_meeting = bool(first_meeting)
        self.last_seen_at = self.started_at
        self.actions: List[str] = []
        self.peer_actions: List[str] = []
        self.items_taken = 0
        self.items_lost = 0
        self.closest_approach = 0.0
        self.closed = False
        self._latest_drives: Dict[str, float] = dict(self.opening_drives)

    # -- during ---------------------------------------------------------
    def observe(self, *, drives: Optional[Dict[str, float]] = None,
                action: str = "", peer_action: str = "",
                proximity: float = 0.0, visible: bool = True,
                now: Optional[float] = None) -> None:
        """One tick of the encounter."""
        stamp = now if now is not None else self.clock()
        if visible:
            self.last_seen_at = stamp
        self.closest_approach = max(self.closest_approach, float(proximity or 0.0))
        # Only note a CHANGE of action. A squid that spends eight seconds
        # fleeing did one thing, not eighty.
        if action and (not self.actions or self.actions[-1] != action):
            self.actions.append(action)
        if peer_action and (not self.peer_actions or self.peer_actions[-1] != peer_action):
            self.peer_actions.append(peer_action)
        if drives:
            self._latest_drives = dict(drives)

    def note_item_taken(self, count: int = 1) -> None:
        self.items_taken += max(0, int(count))

    def note_item_lost(self, count: int = 1) -> None:
        self.items_lost += max(0, int(count))

    # -- closing --------------------------------------------------------
    def should_close(self, now: Optional[float] = None) -> bool:
        stamp = now if now is not None else self.clock()
        if stamp - self.last_seen_at >= LOST_SIGHT_GRACE:
            return True
        return (stamp - self.started_at) >= MAX_ENCOUNTER_DURATION

    def is_memorable(self, now: Optional[float] = None) -> bool:
        """Did enough happen to be worth a memory?

        Duration alone is not the test: a two-second encounter in which a rock
        changed hands is an experience, and a thirty-second one in which two
        squid drifted past each other may not be.
        """
        stamp = now if now is not None else self.clock()
        if self.items_taken or self.items_lost:
            return True
        return (self.last_seen_at - self.started_at) >= MIN_ENCOUNTER_DURATION

    def close(self, drives: Optional[Dict[str, float]] = None,
              now: Optional[float] = None,
              related_neurons: Optional[List[str]] = None) -> EncounterRecord:
        """Finish the encounter and measure how it went."""
        self.closed = True
        record = EncounterRecord(self.peer, self.started_at)
        record.ended_at = now if now is not None else self.clock()
        record.actions = list(self.actions)
        record.peer_actions = list(self.peer_actions)
        record.items_taken = self.items_taken
        record.items_lost = self.items_lost
        record.closest_approach = self.closest_approach
        record.first_meeting = self.first_meeting
        record.related_neurons = list(related_neurons or [])

        closing = dict(drives or getattr(self, '_latest_drives', {}) or {})
        deltas, valence = self._measure(closing)
        record.drive_deltas = deltas
        record.valence = valence
        record.outcome = self._name_outcome(valence, record)
        return record

    def _measure(self, closing: Dict[str, float]):
        """How far the encounter moved the squid, and whether that was good.

        This is measured, not scored from a table of what each action is
        supposed to mean. Two squid can do exactly the same things and have it
        go differently, which is the point.
        """
        deltas: Dict[str, float] = {}
        valence = 0.0
        for drive, weight in OUTCOME_DRIVES.items():
            before = self.opening_drives.get(drive)
            after = closing.get(drive)
            if before is None or after is None:
                continue
            try:
                change = float(after) - float(before)
            except (TypeError, ValueError):
                continue
            if abs(change) < 0.5:
                continue
            deltas[drive] = round(change, 2)
            valence += change * weight
        # Losing an object to another squid is a real loss whether or not the
        # drives happened to register it in the window.
        valence -= self.items_lost * 6.0
        valence += self.items_taken * 4.0
        return deltas, round(valence, 2)

    @staticmethod
    def _name_outcome(valence: float, record: EncounterRecord) -> str:
        """A short label for the Memory tab. Descriptive, never causal.

        This names what the record already contains; nothing downstream reads
        it to decide anything.
        """
        if record.items_lost:
            return "robbed"
        if record.items_taken:
            return "took"
        if valence <= -8.0:
            return "bad"
        if valence >= 8.0:
            return "good"
        return "quiet"


__all__ = ['EncounterSession', 'EncounterRecord', 'OUTCOME_DRIVES',
           'drive_snapshot', 'SNAPSHOT_DRIVES',
           'LOST_SIGHT_GRACE', 'MAX_ENCOUNTER_DURATION',
           'MIN_ENCOUNTER_DURATION']
