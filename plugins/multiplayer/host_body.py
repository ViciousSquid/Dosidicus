# File: host_body.py
"""The host tank as a visiting squid's body and environment.

This is where the invariant lives. The host represents the visitor
physically, tells it what it can see, carries out what it asks for, resolves
what happens, and reports the result. It does not at any point work out what
the visitor should do.

There is exactly one place that could go wrong - `apply_intent` - and the
shape of it is the guarantee: it is a dispatch on an action the visitor's own
network already chose, with no branch anywhere on the visitor's personality,
drives, history or disposition, because none of those are available here.
The host does not have them and is not allowed to ask.

What replaced what
------------------
Before Stage 1, a visitor was driven by RemoteSquidController: a four-state
machine, running on the host, that decided when the visitor explored, fed,
interacted and went home. That is a second squid - a small hand-written one -
standing in for the real brain on the other machine, and everything it decided
was invisible to the real squid's learning. It is not constructed on this
path any more. A visitor whose brain never speaks does not get a stand-in
brain; it stops, and is eventually sent home.
"""

import math
import time
from typing import Any, Dict, List, Optional, Tuple

from .identity import SquidIdentity
from .remote_protocol import (
    ActionIntent, Consequence, PerceptionFrame, ProtocolError,
    CONSEQUENCE_ATE, CONSEQUENCE_BLOCKED, CONSEQUENCE_CONTEST,
    CONSEQUENCE_EJECTED, HEADINGS, INTENT_LEASE, LINK_TIMEOUT,
    OBSERVABLE_SENSORS, VISIT_ABANDON_TIMEOUT,
)

#: How far a visitor moves per applied intent, in pixels. The visitor asks for
#: a direction; how fast a body travels is a property of the tank.
VISITOR_STEP = 18.0

#: Reach for taking or eating something.
GRASP_RANGE = 120.0

#: How far the visitor can see, for the sensors the host computes.
SIGHT_RANGE = 400.0

#: A contest is over an object nearer the resident than the visitor.
CONTEST_RANGE = 400.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _centre(item) -> Tuple[float, float]:
    rect = item.sceneBoundingRect()
    centre = rect.center()
    return float(centre.x()), float(centre.y())


class VisitorActor:
    """A visiting squid's body in this tank. It has no opinions."""

    __slots__ = ('identity', 'visit_id', 'x', 'y', 'facing', 'carrying',
                 'arrived_at', 'last_intent', 'last_intent_at', 'action',
                 'items_taken', 'pending_consequences', 'seq_seen',
                 'has_seen_resident')

    def __init__(self, identity: SquidIdentity, visit_id: str,
                 x: float, y: float, now: float):
        self.identity = identity
        self.visit_id = visit_id
        self.x = float(x)
        self.y = float(y)
        self.facing = 'right'
        self.carrying: Optional[str] = None      # item id, host-issued
        self.arrived_at = now
        self.last_intent: Optional[ActionIntent] = None
        self.last_intent_at = now
        self.action = ''                          # what it is visibly doing
        self.items_taken = 0
        self.pending_consequences: List[Consequence] = []
        self.seq_seen = -1
        #: Whether this visitor has yet been in a position to see the
        #: resident. Observable, and the host is the only party that knows it.
        self.has_seen_resident = False

    @property
    def uuid(self) -> str:
        return self.identity.uuid

    def is_under_control(self, now: float) -> bool:
        """Is a live instruction from the visitor's brain currently in force?"""
        return (self.last_intent is not None
                and self.last_intent.is_live(now))

    def silence(self, now: float) -> float:
        return now - self.last_intent_at


class HostBody:
    """Perception out, intents in, consequences back.

    Constructed with the host's TamagotchiLogic, and reads it defensively -
    every accessor is guarded, so the whole thing is testable against fakes
    and degrades to doing nothing rather than raising into the network thread.
    """

    def __init__(self, tamagotchi_logic=None, conspecific_view=None,
                 clock=time.time, logger=None):
        self.logic = tamagotchi_logic
        self.conspecific_view = conspecific_view
        self.clock = clock
        self.logger = logger
        self.visitors: Dict[str, VisitorActor] = {}     # peer uuid -> actor
        self._item_ids: Dict[str, Any] = {}             # host-issued id -> item
        self._frame_seq = 0
        self.rejected_intents = 0
        #: Visitors that have just laid eyes on the resident for the first
        #: time this visit. Drained by whoever draws the tank.
        self.first_sightings: List[VisitorActor] = []

    # ------------------------------------------------------------------
    # Admitting and removing
    # ------------------------------------------------------------------
    def admit(self, identity: SquidIdentity, visit_id: str,
              x: float, y: float) -> VisitorActor:
        """Give an accepted visitor a body. Consent is decided before this."""
        actor = VisitorActor(identity, visit_id, x, y, self.clock())
        self.visitors[identity.uuid] = actor
        self.publish_presence(actor)
        return actor

    def publish_presence(self, actor: VisitorActor) -> bool:
        """Put the visitor into the RESIDENT's senses.

        Perception has to run both ways or only one squid is in the encounter.
        The host is already telling the visitor where the resident is; this is
        the same fact in the other direction, and it is what lets the
        resident's own conspecific sensors - and therefore its own network -
        respond to having a guest.

        Returns True the first time this visitor is seen, which is the only
        moment a first-sight reaction makes sense.
        """
        view = self.conspecific_view
        resident = self._resident()
        if view is None or resident is None:
            return False
        first_sight = actor.uuid not in view.presences
        view.observe_peer(
            actor.identity, x=actor.x, y=actor.y,
            observer_x=float(getattr(resident, 'squid_x', 0.0)),
            observer_y=float(getattr(resident, 'squid_y', 0.0)),
            facing=str(getattr(resident, 'squid_direction', 'right')),
            status=actor.action, now=self.clock())
        if first_sight and hasattr(resident, 'process_squid_detection'):
            # The resident's own first-sight reaction, through its own senses:
            # the novelty channel, the startle reflex and the notice icon.
            # Keyed on the persistent identity, so a visitor it has met before
            # is not noticed as a stranger.
            try:
                resident.process_squid_detection(actor.uuid, True)
            except Exception as exc:
                self._log(f"resident could not process a first sighting: {exc}")
        return first_sight

    def remove(self, peer_uuid: str) -> Optional[VisitorActor]:
        if self.conspecific_view is not None:
            self.conspecific_view.forget_peer(str(peer_uuid))
        return self.visitors.pop(str(peer_uuid), None)

    def visitor(self, peer_uuid: str) -> Optional[VisitorActor]:
        return self.visitors.get(str(peer_uuid))

    # ------------------------------------------------------------------
    # Host -> visitor: what it can see
    # ------------------------------------------------------------------
    def build_frame(self, actor: VisitorActor) -> PerceptionFrame:
        """Everything the visiting squid can observe from where it is.

        Note what this does not do: it does not consult the visitor's memory,
        because the host does not have it, and it does not compute
        conspecific_familiarity or the recalled-valence sensors. Those are the
        visitor's own record of this resident and are filled in at home. A
        host asserting them would be telling a squid what it remembers.
        """
        now = self.clock()
        # Keep the resident's view of this visitor current on the same tick
        # the visitor is told about the resident.
        self.publish_presence(actor)
        self._frame_seq += 1
        frame = PerceptionFrame(actor.visit_id, seq=self._frame_seq, sent_at=now)
        frame.x, frame.y = actor.x, actor.y
        frame.facing = actor.facing
        frame.tank_width, frame.tank_height = self._tank_size()

        resident = self._resident()
        frame.resident = SquidIdentity.from_squid(resident)

        frame.sensors = self._observable_sensors(actor, resident)
        frame.items = self._observable_items(actor, resident)

        # The moment the visitor could first see the resident. Purely
        # observable - the host computed the sensor itself - so noting it here
        # tells us nothing about what the visitor thinks of what it saw.
        if not actor.has_seen_resident and frame.sensors.get('conspecific_visible'):
            actor.has_seen_resident = True
            self.first_sightings.append(actor)
        return frame

    def drain_first_sightings(self) -> List[VisitorActor]:
        seen, self.first_sightings = self.first_sightings, []
        return seen

    def _observable_sensors(self, actor: VisitorActor, resident) -> Dict[str, float]:
        sensors = {name: 0.0 for name in OBSERVABLE_SENSORS}

        food = self._nearest_of_kind(actor, 'food')
        if food is not None and food[0] <= SIGHT_RANGE:
            sensors['can_see_food'] = 100.0

        plant = self._nearest_of_kind(actor, 'plant')
        if plant is not None:
            sensors['plant_proximity'] = _clamp(
                100.0 - plant[0] / 300.0 * 100.0, 0.0, 100.0)

        # A visitor in an unfamiliar tank has something going on around it.
        # This is the host's own tank activity, not a claim about the visitor.
        sensors['external_stimulus'] = _clamp(
            float(len(self._scene_items('food'))) * 12.0, 0.0, 60.0)

        if resident is not None:
            rx = float(getattr(resident, 'squid_x', 0.0))
            ry = float(getattr(resident, 'squid_y', 0.0))
            dx, dy = rx - actor.x, ry - actor.y
            distance = math.hypot(dx, dy)
            if distance <= SIGHT_RANGE:
                sensors['conspecific_visible'] = 100.0
                sensors['conspecific_proximity'] = _clamp(
                    100.0 - distance / SIGHT_RANGE * 100.0, 0.0, 100.0)
                sensors['conspecific_ahead'] = self._ahead(dx, dy, actor.facing)
                closing = self._resident_closing(actor, distance)
                if closing > 0:
                    sensors['conspecific_closing'] = _clamp(closing / 60.0 * 100.0,
                                                            0.0, 100.0)
                elif closing < 0:
                    sensors['conspecific_receding'] = _clamp(-closing / 60.0 * 100.0,
                                                             0.0, 100.0)
            view = self.conspecific_view
            if view is not None and view.any_contesting(self.clock()):
                sensors['conspecific_contesting'] = 100.0
        return sensors

    def _observable_items(self, actor: VisitorActor, resident) -> List[Dict[str, Any]]:
        """Objects the visitor can see, with host-issued ids.

        The id is opaque and issued here. A visitor can therefore only ever
        name something this tank told it about - it cannot name a file, a
        scene handle or a path, because the protocol has no way to express one.
        """
        items = []
        rx = float(getattr(resident, 'squid_x', 0.0)) if resident else None
        ry = float(getattr(resident, 'squid_y', 0.0)) if resident else None
        for index, item in enumerate(self._scene_items('rock')):
            cx, cy = _centre(item)
            dx, dy = cx - actor.x, cy - actor.y
            if math.hypot(dx, dy) > SIGHT_RANGE:
                continue
            item_id = f"item{index}"
            self._item_ids[item_id] = item
            contested = False
            if rx is not None:
                to_resident = math.hypot(cx - rx, cy - ry)
                contested = to_resident < math.hypot(dx, dy)
            items.append({'id': item_id, 'dx': round(dx, 1),
                          'dy': round(dy, 1), 'contested': contested})
        return items

    # ------------------------------------------------------------------
    # Visitor -> host: carrying out what its brain decided
    # ------------------------------------------------------------------
    def apply_intent(self, actor: VisitorActor, intent: ActionIntent) -> bool:
        """Validate and carry out one instruction. Never decide one.

        Read the dispatch below and note what is not in it: no test of who the
        visitor is, how it is feeling, what it did last time, or what a squid
        of its temperament would presumably do next. The host cannot consult
        any of that - it does not have it - which is what makes "the visitor's
        brain chose this" a structural fact rather than a promise.
        """
        now = self.clock()
        if intent.visit_id != actor.visit_id:
            self.rejected_intents += 1
            return False                       # a stale visit's packet
        if intent.seq <= actor.seq_seen:
            self.rejected_intents += 1
            return False                       # duplicate or out of order
        if not intent.is_live(now):
            self.rejected_intents += 1
            return False                       # arrived after its lease ran out

        actor.seq_seen = intent.seq
        actor.last_intent = intent
        actor.last_intent_at = now
        actor.action = intent.action

        handler = self._ACTIONS.get(intent.action)
        if handler is None:
            # A real action neuron with no bodily effect in someone else's
            # tank (resting, collapsing, inking). Recorded as what the visitor
            # is doing - the resident can see it - and otherwise inert.
            return True
        handler(self, actor, intent)
        return True

    def _do_move(self, actor: VisitorActor, intent: ActionIntent) -> None:
        self._step(actor, intent.heading or actor.facing)

    def _do_eat(self, actor: VisitorActor, intent: ActionIntent) -> None:
        found = self._nearest_of_kind(actor, 'food')
        if found is None:
            return
        distance, item = found
        if distance > GRASP_RANGE:
            self._step_toward(actor, *_centre(item))
            return
        if self._consume(item):
            self._report(actor, CONSEQUENCE_ATE, {'ok': True})
        else:
            self._report(actor, CONSEQUENCE_BLOCKED, {'what': 'eat'})

    def _do_flee(self, actor: VisitorActor, intent: ActionIntent) -> None:
        """Away from the resident - or, with nobody there, away from the middle.

        This is not the host deciding to flee. The visitor's brain decided;
        "away" is a fact about the tank that only the host knows.
        """
        resident = self._resident()
        if resident is not None:
            rx = float(getattr(resident, 'squid_x', 0.0))
            ry = float(getattr(resident, 'squid_y', 0.0))
            self._step_toward(actor, actor.x - (rx - actor.x),
                              actor.y - (ry - actor.y))
            return
        width, height = self._tank_size()
        self._step_toward(actor, actor.x - (width / 2 - actor.x),
                          actor.y - (height / 2 - actor.y))

    def _do_shelter(self, actor: VisitorActor, intent: ActionIntent) -> None:
        found = self._nearest_of_kind(actor, 'plant')
        if found is not None:
            self._step_toward(actor, *_centre(found[1]))

    def _do_play(self, actor: VisitorActor, intent: ActionIntent) -> None:
        """Swim at an object - which is a contest when the resident had a claim.

        There is no separate contest action, here or in the squid. The visitor
        asked to go and get something; whether that something was already
        spoken for is a fact about this tank, and the host is the only party
        that knows it. The resolution below is about reach and possession, not
        a judgement: no aggression table, no dominance score, no social
        interpretation. The environmental change IS the learning signal, at
        both ends.
        """
        item = self._resolve_target(actor, intent, contested_only=False)
        if item is None:
            return
        contested = self._is_contested(item, actor)
        cx, cy = _centre(item)
        if not contested:
            self._step_toward(actor, cx, cy)
            return
        distance = math.hypot(cx - actor.x, cy - actor.y)
        if distance > GRASP_RANGE:
            self._step_toward(actor, cx, cy)
            return

        resident = self._resident()
        held_by_resident = bool(getattr(resident, 'carrying_rock', False) and
                                getattr(resident, 'current_rock', None) is item)
        if held_by_resident:
            # It is in the resident's grasp. The resident keeps it, and both
            # squid have now been in a contest.
            self._report(actor, CONSEQUENCE_CONTEST,
                         {'won': False, 'reason': 'held'})
            self._note_contest(actor, item, taken=False)
            return

        actor.carrying = intent.target_id or getattr(item, 'filename', 'item')
        actor.items_taken += 1
        self._take_from_scene(item)
        self._report(actor, CONSEQUENCE_CONTEST, {'won': True})
        self._note_contest(actor, item, taken=True)

    def _is_contested(self, item, actor: VisitorActor) -> bool:
        """Is this object nearer the resident than the visitor?"""
        resident = self._resident()
        if resident is None:
            return False
        cx, cy = _centre(item)
        to_resident = math.hypot(cx - float(getattr(resident, 'squid_x', 0.0)),
                                 cy - float(getattr(resident, 'squid_y', 0.0)))
        return to_resident < math.hypot(cx - actor.x, cy - actor.y)

    #: The dispatch table. Keyed by ACTION NEURON, so the host's whole
    #: vocabulary is what the squid's own network can want - there is no
    #: entry here that does not correspond to something the visiting squid's
    #: own action neurons could have chosen. Actions absent (act_ink,
    #: act_rest, act_collapse) are visible to the resident but have no effect
    #: on someone else's tank.
    _ACTIONS = {
        'act_move': _do_move,
        'act_eat': _do_eat,
        'act_flee': _do_flee,
        'act_shelter': _do_shelter,
        'act_play': _do_play,
    }

    # ------------------------------------------------------------------
    # The link
    # ------------------------------------------------------------------
    def tick(self) -> List[Tuple[VisitorActor, str]]:
        """Housekeeping. Returns visitors whose visit the host is ending.

        Two timeouts, and no prediction between them. A visitor whose brain
        has gone quiet STOPS - it does not carry on with its last instruction,
        and it does not get a stand-in policy to keep it looking alive. Both
        of those would be the host inventing behaviour, and the second would
        be the thing this stage exists to remove.
        """
        now = self.clock()
        ending = []
        for actor in list(self.visitors.values()):
            silence = actor.silence(now)
            if silence >= VISIT_ABANDON_TIMEOUT:
                self._report(actor, CONSEQUENCE_EJECTED, {'reason': 'link_lost'})
                ending.append((actor, 'link_lost'))
                continue
            if silence >= LINK_TIMEOUT and not actor.is_under_control(now):
                # Deterministic and visibly inert, so a stalled visitor reads
                # as a stalled visitor rather than as a squid behaving oddly.
                actor.action = 'stalled'
        return ending

    def drain_consequences(self, actor: VisitorActor) -> List[Consequence]:
        pending, actor.pending_consequences = actor.pending_consequences, []
        return pending

    # ------------------------------------------------------------------
    # Reaching into the host tank, defensively
    # ------------------------------------------------------------------
    def _resident(self):
        return getattr(self.logic, 'squid', None)

    def _tank_size(self) -> Tuple[float, float]:
        ui = getattr(self.logic, 'user_interface', None)
        return (float(getattr(ui, 'window_width', 1280.0)),
                float(getattr(ui, 'window_height', 900.0)))

    def _scene_items(self, category: str) -> List[Any]:
        if category == 'food':
            return list(getattr(self.logic, 'food_items', []) or [])
        ui = getattr(self.logic, 'user_interface', None)
        scene = getattr(ui, 'scene', None)
        if scene is None:
            return []
        try:
            return [i for i in scene.items()
                    if getattr(i, 'category', '') == category]
        except Exception:
            return []

    def _nearest_of_kind(self, actor: VisitorActor,
                         category: str) -> Optional[Tuple[float, Any]]:
        best = None
        for item in self._scene_items(category):
            try:
                cx, cy = _centre(item)
            except Exception:
                continue
            distance = math.hypot(cx - actor.x, cy - actor.y)
            if best is None or distance < best[0]:
                best = (distance, item)
        return best

    def _resolve_target(self, actor: VisitorActor, intent: ActionIntent,
                        contested_only: bool):
        """Turn the visitor's item id back into an object in this tank.

        Only ids this host issued resolve to anything, so an id the visitor
        invented finds nothing rather than reaching an arbitrary object.
        """
        if intent.target_id:
            item = self._item_ids.get(intent.target_id)
            if item is not None and self._still_present(item):
                return item
            return None
        found = self._nearest_of_kind(actor, 'rock')
        if found is None or found[0] > CONTEST_RANGE:
            return None
        if contested_only:
            resident = self._resident()
            if resident is None:
                return None
            cx, cy = _centre(found[1])
            to_resident = math.hypot(cx - float(getattr(resident, 'squid_x', 0.0)),
                                     cy - float(getattr(resident, 'squid_y', 0.0)))
            if to_resident >= found[0]:
                return None            # nearer to us: foraging, not a contest
        return found[1]

    def _still_present(self, item) -> bool:
        ui = getattr(self.logic, 'user_interface', None)
        scene = getattr(ui, 'scene', None)
        if scene is None:
            return True
        try:
            return item in scene.items()
        except Exception:
            return True

    def _take_from_scene(self, item) -> None:
        ui = getattr(self.logic, 'user_interface', None)
        scene = getattr(ui, 'scene', None)
        if scene is None:
            return
        try:
            if item in scene.items():
                scene.removeItem(item)
        except Exception as exc:
            self._log(f"could not remove a contested item: {exc}")

    def _consume(self, item) -> bool:
        logic = self.logic
        try:
            food = getattr(logic, 'food_items', None)
            if food is not None and item in food:
                food.remove(item)
            self._take_from_scene(item)
            return True
        except Exception as exc:
            self._log(f"could not consume food for a visitor: {exc}")
            return False

    def _note_contest(self, actor: VisitorActor, item, taken: bool) -> None:
        """Make the contest perceptible to the RESIDENT, through its senses.

        The resident learns about this the same way it learns about anything:
        its conspecific_contesting sensor comes on, and whatever that does to
        its drives is what its own network has to work with.
        """
        view = self.conspecific_view
        if view is None or not hasattr(view, 'note_contest'):
            return
        presence = view.presences.get(actor.uuid)
        rival = presence if presence is not None else actor
        try:
            view.note_contest(rival, item, taken=taken)
        except Exception as exc:
            self._log(f"could not record a contest: {exc}")

    # ------------------------------------------------------------------
    def _step(self, actor: VisitorActor, heading: str) -> None:
        if heading not in HEADINGS:
            return
        dx = {'left': -VISITOR_STEP, 'right': VISITOR_STEP}.get(heading, 0.0)
        dy = {'up': -VISITOR_STEP, 'down': VISITOR_STEP}.get(heading, 0.0)
        width, height = self._tank_size()
        actor.x = _clamp(actor.x + dx, 0.0, width)
        actor.y = _clamp(actor.y + dy, 0.0, height)
        actor.facing = heading

    def _step_toward(self, actor: VisitorActor, x: float, y: float) -> None:
        dx, dy = x - actor.x, y - actor.y
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return
        if abs(dx) >= abs(dy):
            self._step(actor, 'right' if dx > 0 else 'left')
        else:
            self._step(actor, 'down' if dy > 0 else 'up')

    def _report(self, actor: VisitorActor, kind: str,
                detail: Optional[Dict[str, Any]] = None) -> Consequence:
        consequence = Consequence(actor.visit_id, kind, self.clock(), detail)
        actor.pending_consequences.append(consequence)
        return consequence

    @staticmethod
    def _ahead(dx: float, dy: float, facing: str) -> float:
        vectors = {'right': (1.0, 0.0), 'left': (-1.0, 0.0),
                   'up': (0.0, -1.0), 'down': (0.0, 1.0)}
        vector = vectors.get(facing)
        length = math.hypot(dx, dy)
        if vector is None or length < 1e-6:
            return 0.0
        cosine = (dx * vector[0] + dy * vector[1]) / length
        return _clamp((cosine + 1.0) * 50.0, 0.0, 100.0)

    def _resident_closing(self, actor: VisitorActor, distance: float) -> float:
        view = self.conspecific_view
        if view is None:
            return 0.0
        presence = view.presences.get(actor.uuid)
        return float(getattr(presence, 'closing_rate', 0.0) or 0.0)

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.debug(f"[HostBody] {message}")


__all__ = ['HostBody', 'VisitorActor', 'VISITOR_STEP', 'GRASP_RANGE',
           'SIGHT_RANGE', 'CONTEST_RANGE']
