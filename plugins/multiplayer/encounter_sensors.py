# File: encounter_sensors.py
"""Another squid, as something the brain can sense.

These are ordinary input sensors. They go in through
`PluginManager.register_neuron_handler` like any plugin sensor, and they are
classified through `brain_constants.register_input_sensor` so that the four
systems which reason about pure inputs - propagation's resting levels, the
capability monitor's situation signatures, the causal ledger's cues, and the
rule about what a learned synapse may point at - all see them as sense organs.

Every one of them rests at ZERO, and zero always means "nothing to report".
That is why there is no single signed "how do I feel about this squid"
sensor: a neutral reading of 50 would be indistinguishable from a real
mid-strength signal, and a squid that has never met anyone would be born with
half a sensation of something. Anything with two directions is therefore two
sensors in push-pull - closing and receding, recalled-good and recalled-bad -
which is the same shape the engine's own regulators take.

What is NOT here:

  * no mapping from "another squid" to any action. Nothing in this module
    knows what fleeing is. The sensors report; the action neurons compete;
    the decision engine reads the winner.
  * no social neuron type, and no growth. If an encounter turns out to be
    something the network cannot represent, the existing capability monitor
    will notice on its own evidence and say so.
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional

from .identity import SquidIdentity

#: (name, binary, position, description). The position is where the neuron
#: would like to sit if it is drawn; brain_constants keeps these apart from
#: the built-in layout so the default brain is untouched.
SENSOR_SPECS = (
    ('conspecific_visible', True, (350, 50),
     'Another squid is in view'),
    ('conspecific_proximity', False, (350, 150),
     'How close the nearest other squid is'),
    ('conspecific_ahead', False, (350, 250),
     'How squarely the other squid is in front of this one'),
    ('conspecific_closing', False, (350, 350),
     'The other squid is getting closer'),
    ('conspecific_receding', False, (450, 50),
     'The other squid is moving away'),
    ('conspecific_familiarity', False, (450, 150),
     'How well this individual is known'),
    ('conspecific_recalled_good', False, (450, 250),
     'Past encounters with this individual went well'),
    ('conspecific_recalled_bad', False, (450, 350),
     'Past encounters with this individual went badly'),
    ('conspecific_contesting', True, (550, 50),
     'The other squid is contesting an object with this one'),
)

SENSOR_NAMES = tuple(spec[0] for spec in SENSOR_SPECS)

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
                 'status', 'last_update', 'contest_until', '_last_distance',
                 '_last_distance_at')

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
    def nearest(self, now: Optional[float] = None) -> Optional[ConspecificPresence]:
        """The other squid this one would be reacting to, if any."""
        stamp = now if now is not None else self.clock()
        live = [p for p in self.presences.values()
                if stamp - p.last_update <= PRESENCE_TIMEOUT]
        if not live:
            return None
        return min(live, key=lambda p: p.distance)

    def any_contesting(self, now: Optional[float] = None) -> bool:
        stamp = now if now is not None else self.clock()
        return any(p.is_contesting(stamp) for p in self.presences.values())

    # -- consequences ---------------------------------------------------
    def note_contest(self, rival, item=None, taken: bool = False,
                     squid=None, now: Optional[float] = None) -> None:
        """A contest happened with this squid. Called by the actuator.

        Recorded rather than scored: what it did to either squid is measured
        from their drives when the encounter closes, not decided here.
        """
        stamp = now if now is not None else self.clock()
        presence = self.presences.get(getattr(rival, 'uuid', ''))
        if presence is not None:
            presence.contest_until = stamp + CONTEST_LINGER
        self._contest_log.append({
            'peer_uuid': getattr(rival, 'uuid', ''),
            'taken': bool(taken),
            'at': stamp,
            'item': getattr(item, 'filename', None),
        })
        if len(self._contest_log) > 50:
            del self._contest_log[:-50]

    def drain_contests(self) -> List[Dict[str, Any]]:
        """Contests since the last call, for the encounter session to file."""
        log, self._contest_log = self._contest_log, []
        return log


class EncounterSensors:
    """Registers the conspecific sensors and computes their values."""

    def __init__(self, view: ConspecificView, ledger=None, clock=time.time):
        self.view = view
        self.ledger = ledger
        self.clock = clock
        self._registered: List[str] = []

    # -- the sensors ----------------------------------------------------
    def handlers(self) -> Dict[str, Callable[[], float]]:
        return {
            'conspecific_visible': self.visible,
            'conspecific_proximity': self.proximity,
            'conspecific_ahead': self.ahead,
            'conspecific_closing': self.closing,
            'conspecific_receding': self.receding,
            'conspecific_familiarity': self.familiarity,
            'conspecific_recalled_good': self.recalled_good,
            'conspecific_recalled_bad': self.recalled_bad,
            'conspecific_contesting': self.contesting,
        }

    def _nearest(self) -> Optional[ConspecificPresence]:
        return self.view.nearest(self.clock())

    def visible(self) -> float:
        return 100.0 if self._nearest() is not None else 0.0

    def proximity(self) -> float:
        """Closer reads higher, on the same shape as plant_proximity."""
        nearest = self._nearest()
        if nearest is None:
            return 0.0
        return _clamp(100.0 - (nearest.distance / PROXIMITY_RANGE * 100.0))

    def ahead(self) -> float:
        nearest = self._nearest()
        return 0.0 if nearest is None else _clamp(nearest.ahead)

    def closing(self) -> float:
        nearest = self._nearest()
        if nearest is None or nearest.closing_rate <= 0:
            return 0.0
        return _clamp(nearest.closing_rate / FULL_CLOSING_SPEED * 100.0)

    def receding(self) -> float:
        nearest = self._nearest()
        if nearest is None or nearest.closing_rate >= 0:
            return 0.0
        return _clamp(-nearest.closing_rate / FULL_CLOSING_SPEED * 100.0)

    def familiarity(self) -> float:
        """Zero for a squid never met before, which is the whole point.

        A stranger is not represented by a special case or a default guess -
        it is represented by a sense organ with nothing to report, which is
        exactly what uncertainty about an unfamiliar individual is.
        """
        nearest = self._nearest()
        if nearest is None or self.ledger is None:
            return 0.0
        return _clamp(self.ledger.familiarity(nearest.uuid))

    def recalled_good(self) -> float:
        nearest = self._nearest()
        if nearest is None or self.ledger is None:
            return 0.0
        return _clamp(self.ledger.recalled_good(nearest.uuid))

    def recalled_bad(self) -> float:
        nearest = self._nearest()
        if nearest is None or self.ledger is None:
            return 0.0
        return _clamp(self.ledger.recalled_bad(nearest.uuid))

    def contesting(self) -> float:
        return 100.0 if self.view.any_contesting(self.clock()) else 0.0

    # -- registration ---------------------------------------------------
    def register(self, plugin_manager, brain_constants, plugin_name='Multiplayer',
                 brain_widget=None) -> List[str]:
        """Make these sensors real, in all three places they have to be real.

        1. the plugin manager, so BrainNeuronHooks will call them;
        2. brain_constants, so every system that reasons about pure inputs
           treats them as sense organs;
        3. the brain itself, because BrainNeuronHooks only reads handlers for
           neurons that actually exist in neuron_positions.

        Step 2 is the one that did not previously exist, and without it the
        first and third are decoration: the value would reach brain_state and
        nothing structural would ever be able to use it.
        """
        handlers = self.handlers()
        for name, binary, position, description in SENSOR_SPECS:
            brain_constants.register_input_sensor(
                name, binary=binary, position=position, owner=plugin_name.lower())
            plugin_manager.register_neuron_handler(
                neuron_name=name,
                handler=handlers[name],
                plugin_name=plugin_name,
                metadata={
                    'description': description,
                    'is_binary': binary,
                    'category': 'conspecific',
                    'source': 'plugin',
                },
            )
            self._registered.append(name)
        if brain_widget is not None:
            self.attach_to_brain(brain_widget)
        return list(self._registered)

    def attach_to_brain(self, brain_widget) -> List[str]:
        """Add the sensor neurons to a live brain that does not have them.

        BrainNeuronHooks iterates the brain's own neurons and only asks for a
        value where the neuron exists, so registration alone is not enough for
        anything to happen.
        """
        added = []
        positions = getattr(brain_widget, 'neuron_positions', None)
        state = getattr(brain_widget, 'state', None)
        if positions is None or state is None:
            return added
        for name, _binary, position, _description in SENSOR_SPECS:
            if name not in positions:
                positions[name] = tuple(position)
                added.append(name)
            # A sense organ rests at zero whether it is new or restored.
            state.setdefault(name, 0.0)
        return added

    def unregister(self, plugin_manager, plugin_name='Multiplayer') -> None:
        """Stop supplying values when the plugin is disabled.

        Two things are deliberately NOT undone here.

        The neurons stay in the brain. Removing one would throw away every
        synapse the squid had learned onto it, and the squid did learn those -
        switching the plugin off is not a reason to pretend it never met
        anyone.

        The sensor CLASSIFICATION also stays. Those neurons are still sense
        organs: they still rest at zero, and forward propagation still must
        not write them. Unregistering the classification while the neurons
        remain would hand them straight back to propagation, which is the
        exact bug this whole seam exists to prevent. With the handler gone
        they simply report nothing, which is the truth.

        `release_classification` exists for the case where the neurons really
        are going away - tests, mostly, which must not leak module-level state
        into one another.
        """
        for name in list(self._registered):
            try:
                plugin_manager.unregister_neuron_handler(name, plugin_name)
            except Exception:
                pass
        self._registered = []

    @staticmethod
    def release_classification(brain_constants) -> None:
        """Forget that these names are sensors. Only safe with no live brain."""
        for name, _binary, _position, _description in SENSOR_SPECS:
            brain_constants.unregister_input_sensor(name)


__all__ = ['ConspecificView', 'ConspecificPresence', 'EncounterSensors',
           'SENSOR_SPECS', 'SENSOR_NAMES', 'PROXIMITY_RANGE',
           'FULL_CLOSING_SPEED', 'CONTEST_LINGER', 'PRESENCE_TIMEOUT']
