# File: visitor_mind.py
"""The visiting squid's end of the round trip. This is where its brain is.

A squid that has swum into someone else's tank still lives here. Its network,
its weights, its memories, its capability ledger and its neurogenesis all
carry on running in this process, on this machine. What has changed is only
where its senses point and where its actions land:

    host's perception_frame                       -> RemotePerception
        -> the SAME BrainNeuronHooks sensors it always had
            -> the SAME propagation
                -> the SAME action neurons, competing as they always do
                    -> decision_engine.select_action  (the same rule)
                        -> ActionIntent -> the host

Nothing here chooses a behaviour. The only thing this module does with the
decision is name it and put it in an envelope.

WHY THE PERCEPTION GOES THROUGH THE ORDINARY SENSORS
----------------------------------------------------
It would be shorter to hand the host's numbers straight to select_action. It
would also be wrong: everything that makes an experience learnable in this
engine hangs off the sensors being real sensors. The capability monitor builds
its situation signatures from PURE_INPUT_NEURONS, the causal ledger takes its
cues from them, and plasticity reads their activations. A visit whose
perception bypassed them would be a visit the squid could not learn anything
from - which is exactly the state Stage 0 existed to get out of.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from .encounter import EncounterSession, drive_snapshot
from .identity import SquidIdentity
from .remote_protocol import (
    ActionIntent, Consequence, PerceptionFrame, ProtocolError, VisitEnd,
    CONSEQUENCE_ATE, CONSEQUENCE_BLOCKED, CONSEQUENCE_CONTEST,
    CONSEQUENCE_EJECTED, CONSEQUENCE_MATED, CONSEQUENCE_FIGHT, CONSEQUENCE_HIT,
    CONSEQUENCE_THROWN,
    END_DEPARTED, END_LINK_LOST, HEADINGS,
    INTENT_LEASE, LINK_TIMEOUT, OBSERVABLE_SENSORS, new_visit_id,
)

#: Built-in sensors whose value comes from the host while the squid is away.
#: Everything else a squid senses is about its own body - whether it is sick,
#: asleep, startled, how threatened it feels - and stays local, because those
#: are true wherever it happens to be swimming.
REMOTE_DRIVEN_SENSORS = ('can_see_food', 'plant_proximity', 'external_stimulus')

#: What being away does to a squid, as ordinary drive changes rather than as
#: an interpretation. Applied once when a consequence arrives, so that what
#: happened in the other tank reaches the drives the causal ledger measures.
_ATE_HUNGER_RELIEF = 12.0
_CONTEST_WON_SATISFACTION = 8.0
_CONTEST_LOST_ANXIETY = 6.0
_BLOCKED_SATISFACTION = 2.0


#: What brings a visiting squid home, when its own network chooses it: flight
#: (a frightened squid swims home) or rest (it goes home to sleep - always: a
#: squid that is asleep while away comes home on the next tick, however it
#: fell asleep). With the thought it has about it.
HOMEWARD = {
    'act_flee': "I was frightened, so I swam home.",
    'act_rest': "I am tired: I went home to sleep.",
    'act_collapse': "I am exhausted: I went home to sleep.",
}


class RemotePerception:
    """The last thing the host said the visiting squid could see.

    Holds one frame. Every sensor handler reads it while away and falls
    through to the local one at home, so a single registration covers both and
    there is no churn at the boundary of a visit.
    """

    def __init__(self, clock=time.time):
        self.clock = clock
        self.away = False
        self.visit_id = ''
        self.frame: Optional[PerceptionFrame] = None
        self.received_at = 0.0
        self.resident: Optional[SquidIdentity] = None
        self.frames_seen = 0
        self.last_seq = -1

    # -- lifecycle ------------------------------------------------------
    def begin(self, visit_id: str) -> None:
        self.away = True
        self.visit_id = visit_id
        self.frame = None
        self.received_at = self.clock()
        self.resident = None
        self.last_seq = -1

    def end(self) -> None:
        self.away = False
        self.visit_id = ''
        self.frame = None
        self.resident = None

    def accept(self, frame: PerceptionFrame) -> bool:
        """Take a frame if it belongs to this visit and is not stale.

        The HOST names the visit, because the host is the one that decided to
        allow it. A visitor that has been let in but not yet told what the
        visit is called adopts the name on the first frame; after that the
        name is fixed, so a packet from a previous visit to the same tank is
        ignored rather than resurrecting it.
        """
        if not self.away:
            return False
        if not self.visit_id:
            self.visit_id = frame.visit_id
        elif frame.visit_id != self.visit_id:
            return False
        if frame.seq <= self.last_seq:
            return False          # duplicate, or arrived out of order
        self.last_seq = frame.seq
        self.frame = frame
        self.received_at = self.clock()
        self.resident = frame.resident
        self.frames_seen += 1
        return True

    # -- reading --------------------------------------------------------
    @property
    def linked(self) -> bool:
        """Is the host still talking to us?"""
        return (self.away and self.frame is not None
                and (self.clock() - self.received_at) < LINK_TIMEOUT)

    def sensor(self, name: str, default: float = 0.0) -> float:
        if not self.linked:
            return default
        return float(self.frame.sensors.get(name, default))

    def resident_uuid(self) -> str:
        return self.resident.uuid if self.resident else ''


class VisitorMind:
    """Turns host perception into this squid's own decision, and back.

    Owns nothing about behaviour. It wires the host's frame into the sensors,
    asks the squid's own network what it wants, and posts the answer.
    """

    def __init__(self, tamagotchi_logic=None, peer_ledger=None,
                 send=None, clock=time.time, logger=None):
        self.logic = tamagotchi_logic
        self.peer_ledger = peer_ledger
        self.send = send or (lambda message_type, payload: None)
        self.clock = clock
        self.logger = logger
        self.perception = RemotePerception(clock=clock)
        self.visit_id = ''
        self.host_uuid = ''
        self.intents_sent = 0
        self.last_intent: Optional[ActionIntent] = None
        self.consequences: List[Consequence] = []
        #: The visit, as an experience this squid is having. Opened when the
        #: host names its resident and closed when the visit ends, at which
        #: point it becomes an ordinary memory keyed to that individual.
        #:
        #: Before Stage 2A a visiting squid recorded nothing at all: it could
        #: READ what it remembered about a resident but never wrote anything
        #: new, so the loop that is supposed to make a second encounter
        #: different from a first was open at exactly the point that matters.
        self.session: Optional[EncounterSession] = None
        self._seq = 0
        self._restore: Dict[str, Callable] = {}
        #: Told whether this squid won, once per fight it records while
        #: visiting. Used to announce the fight; it decides nothing.
        self.on_fight: Optional[Callable[[bool], None]] = None
        #: Its half of a hatchling's weights, made once per mating and resent
        #: with each retelling of the news.
        self._gametes: Dict[str, Dict[str, float]] = {}
        # Retained for this mind's lifetime: a repeated UDP consequence must
        # never repeat an irreversible physical or remembered consequence.
        self._rock_hits = set()
        self._inking = False
        self._resisting_sleep = False     # a stubborn squid holding off sleep

    # ==================================================================
    # Perception: the host's frame, through the ordinary sensor path
    # ==================================================================
    def sensor_overrides(self, builtin_handlers: Dict[str, Callable]
                         ) -> Dict[str, Callable[[], float]]:
        """Wrappers for the built-in sensors, for the plugin to register.

        Each one reads the host's frame while the squid is away and the
        original handler while it is at home, so the squid has exactly one set
        of sense organs for its whole life and they simply point somewhere else
        for the duration of a visit.
        """
        overrides = {}
        for name in REMOTE_DRIVEN_SENSORS:
            original = builtin_handlers.get(name)
            overrides[name] = self._make_override(name, original)
        return overrides

    def _make_override(self, name: str, original: Optional[Callable]
                       ) -> Callable[[], float]:
        def read() -> float:
            if self.perception.linked:
                return self.perception.sensor(name, 0.0)
            if original is None:
                return 0.0
            try:
                return float(original())
            except Exception:
                return 0.0
        read.__name__ = f"remote_or_local_{name}"
        return read

    def on_perception_frame(self, payload: Dict[str, Any]) -> bool:
        """A frame arrived from the host."""
        try:
            frame = PerceptionFrame.from_payload(payload)
        except ProtocolError as exc:
            self._log(f"rejected a perception frame: {exc}")
            return False
        accepted = self.perception.accept(frame)
        if accepted:
            # The host names the visit; adopt it here too, so a visit_end or
            # a consequence for this visit is recognised even before this
            # squid has had a chance to decide anything.
            self.visit_id = self.perception.visit_id
            self._open_session()
            # What its senses report in the host tank, as they would at home:
            # the resident in view or not, how close, a scuffle - and, from
            # its own memory, whether it knows the squid it is looking at.
            self._perceive_host_tank()
        return accepted

    def _perceive_host_tank(self, away: bool = True) -> None:
        from .encounter import perceive_recognition
        window = getattr(self.logic, 'brain_window', None)
        widget = getattr(window, 'brain_widget', None)
        if not hasattr(widget, 'perceive'):
            return
        sense = (lambda name: self.perception.sensor(name, 0.0)) if away else (lambda name: 0.0)
        in_view = sense('squid_in_view')
        widget.perceive('squid_in_view', in_view)
        widget.perceive('squid_proximity', sense('squid_proximity'))
        widget.perceive('in_fight', sense('in_fight'))
        resident = self.perception.resident if away and in_view > 0 else None
        perceive_recognition(widget, self.peer_ledger,
                             getattr(resident, 'uuid', '') if resident else '')

    def _open_session(self) -> None:
        """Start recording the experience, once we know whose tank this is.

        The resident's identity arrives with the first frame, and an
        experience has to be filed against an individual or it is not the kind
        of memory this stage is about - so the session cannot exist before
        then.
        """
        if self.session is not None or not self.perception.resident:
            return
        squid = getattr(self.logic, 'squid', None)
        first_meeting = True
        if self.peer_ledger is not None:
            first_meeting = (
                self.peer_ledger.summary(self.perception.resident.uuid).encounters == 0)
        self.session = EncounterSession(
            self.perception.resident, drive_snapshot(squid),
            first_meeting=first_meeting, now=self.clock(), clock=self.clock)
        self._log(f"Encounter opened with {self.perception.resident} "
                  f"(first meeting: {first_meeting})")
        say = getattr(self.logic, 'show_message', None)
        if callable(say):               # its own tank says where it has gone
            say(f"{getattr(squid, 'name', 'Your squid')} is visiting "
                f"{self.perception.resident.name}'s tank")

    # ==================================================================
    # Decision: the squid's own network, and the engine's own rule
    # ==================================================================
    def decide(self) -> Optional[ActionIntent]:
        """Ask this squid's brain what it wants, and post it to the host.

        The brain state read here is the one the ordinary game loop has just
        propagated, from sensors the host's frame is currently driving. The
        selection is decision_engine.select_action - the same function the
        squid uses at home - so a visiting squid and a squid that stayed in
        would make the same choice from the same network. That is the whole
        claim of this stage, and it is a fact about which function is called
        rather than a promise about behaviour.
        """
        if not self.perception.linked:
            return None
        self.visit_id = self.perception.visit_id
        brain_state = self._brain_state()
        if not brain_state:
            return None

        from src.decision_engine import select_action, wants, action_activations
        from src.brain_constants import (ACTION_BEHAVIOURS, FALLBACK_ACTION,
                                         ACTION_THRESHOLDS)

        # Exhaustion is a reflex, outside the competition, and nothing resists
        # it: an exhausted squid goes home to sleep.
        if wants('act_collapse', float(brain_state.get('act_collapse', 0.0) or 0.0)):
            self.go_home('act_collapse')
            return None

        behaviour, confidence, _urgency = select_action(brain_state)
        if behaviour is None:
            # Nothing cleared its own threshold. Locomotion is the fallback,
            # and it has to clear its threshold like anything else - so a
            # sleeping squid, whose act_move is held down by the sleep gating,
            # sends no intent at all and its body in the other tank stops.
            locomotion = action_activations(brain_state).get(
                ACTION_BEHAVIOURS[FALLBACK_ACTION], 0.0)
            if not wants(FALLBACK_ACTION, locomotion):
                return None
            behaviour = ACTION_BEHAVIOURS[FALLBACK_ACTION]

        action = self._neuron_for(behaviour)
        if action is None:
            return None

        # Fear or tiredness takes it home: its own network's flight, or its
        # rest, winning the competition ends the visit - no timer, no host.
        # A stubborn squid can hold off sleep for a while (never exhaustion,
        # never past personality.STUBBORN_SLEEP_LIMIT) and does the next thing
        # its network wants instead.
        from src.personality import RESISTED_SLEEP, squid_resists_sleep
        squid = getattr(self.logic, 'squid', None)
        resisting = action == 'act_rest' and squid_resists_sleep(squid)
        if resisting and not self._resisting_sleep:
            window = getattr(self.logic, 'brain_window', None)
            if hasattr(window, 'add_thought'):
                window.add_thought(RESISTED_SLEEP)
        self._resisting_sleep = resisting
        if resisting:
            awake = {b: u for b, u in (_urgency or {}).items() if b != behaviour}
            behaviour = max(awake, key=awake.get) if awake else ACTION_BEHAVIOURS[FALLBACK_ACTION]
            action = self._neuron_for(behaviour)
            if action is None or action in HOMEWARD:
                return None
        elif action in HOMEWARD:
            self.go_home(action)
            return None

        # The encounter is being had, not just transacted: what this squid did
        # and how its drives moved while it was here are what the record is
        # made of when the visit ends.
        if self.session is not None:
            self.session.observe(
                drives=drive_snapshot(getattr(self.logic, 'squid', None)),
                action=behaviour,
                proximity=self.perception.sensor('squid_proximity', 0.0),
                visible=bool(self.perception.sensor('squid_in_view', 0.0)),
                now=self.clock())

        # How it would fight, from its own brain and body, for the host to
        # resolve a fight with: its aggression neuron, how hard it would
        # fight back, and its fitness (src/fighting.py).
        from src.fighting import commitment, fight_predisposition, squid_fitness
        from src.throwing import practice_of
        squid = getattr(self.logic, 'squid', None)
        self._seq += 1
        intent = ActionIntent(
            visit_id=self.visit_id,
            action=action,
            seq=self._seq,
            sent_at=self.clock(),
            activation=float(brain_state.get(action, 0.0) or 0.0),
            confidence=confidence,
            heading=self._heading_for(action, brain_state),
            target_id=self._target_for(action),
            lease=INTENT_LEASE,
            aggression=fight_predisposition(brain_state)[0],
            defence=commitment(brain_state, attacking=False)[0],
            fitness=squid_fitness(squid)[0] if squid is not None else 1.0,
            # Its own throwing record at home: the squid's statistics on
            # desktop, the game's on mobile.
            practice=practice_of(getattr(squid, 'statistics', None),
                                 getattr(self.logic, 'stats', None)),
        )
        self.last_intent = intent
        self.intents_sent += 1
        self.send('action_intent', intent.to_payload())
        return intent

    @staticmethod
    def _neuron_for(behaviour: str) -> Optional[str]:
        from src.brain_constants import ACTION_BEHAVIOURS
        for neuron, name in ACTION_BEHAVIOURS.items():
            if name == behaviour:
                return neuron
        return None

    def _heading_for(self, action: str, brain_state: Dict[str, float]) -> str:
        """Which way to go, for actions that are just movement.

        Everything directional the host can work out for itself (toward the
        food it can see, away from its resident) is left to the host, because
        the host is the one that knows where those things are. This only
        answers the case where the squid wants to swim and nothing in the
        frame says where: it keeps going the way it was pointed.
        """
        if action != 'act_move':
            return ''
        frame = self.perception.frame
        if frame is None:
            return ''
        # Toward whatever it can see, if anything; otherwise carry on.
        item = frame.nearest_item()
        if item is not None:
            if abs(item['dx']) >= abs(item['dy']):
                return 'right' if item['dx'] > 0 else 'left'
            return 'down' if item['dy'] > 0 else 'up'
        return frame.facing if frame.facing in HEADINGS else 'right'

    def _target_for(self, action: str) -> str:
        """Which object the squid is going for, if it wants one.

        Deliberately not filtered by whether the object is contested. The
        squid asks for the nearest thing it can see; whether another squid had
        a claim to it is something the host resolves, and something the squid
        finds out by what happens next.
        """
        if action != 'act_play':
            return ''
        frame = self.perception.frame
        if frame is None:
            return ''
        item = frame.nearest_item()
        return item['id'] if item else ''

    # ==================================================================
    # Consequence: what happened, back into the senses
    # ==================================================================
    def on_consequence(self, payload: Dict[str, Any]) -> Optional[Consequence]:
        """Fold an observable result back into this squid's own state.

        Deliberately expressed as drive changes and a memory, not as a verdict.
        Nothing here says a lost contest was bad - it says the squid's anxiety
        went up, which is the evidence the causal ledger measures and the
        material Hebbian learning works on. What the squid makes of it is its
        network's business.
        """
        try:
            consequence = Consequence.from_payload(payload)
        except ProtocolError as exc:
            self._log(f"rejected a consequence: {exc}")
            return None
        if consequence.visit_id != self.visit_id:
            return None

        if consequence.kind in (CONSEQUENCE_HIT, CONSEQUENCE_THROWN):
            throw_id = consequence.detail.get('throw_id')
            if not isinstance(throw_id, str) or not throw_id.strip():
                return None
            key = (consequence.visit_id, throw_id, consequence.kind,
                   consequence.detail.get('taken', True))
            if key in self._rock_hits:
                return None
            self._rock_hits.add(key)
        self.consequences.append(consequence)
        squid = getattr(self.logic, 'squid', None)
        if squid is None:
            return consequence

        kind, detail = consequence.kind, consequence.detail

        if kind == CONSEQUENCE_FIGHT:
            fight_id, won = detail.get('fight_id'), detail.get('won')
            stats = getattr(squid, 'statistics', None)
            if (isinstance(fight_id, str) and 0 < len(fight_id) <= 64
                    and isinstance(won, bool) and stats is not None):
                if stats.record_fight_result(fight_id, won):
                    self._live_through_fight(squid, fight_id, won, detail)
                    if self.session is not None:
                        self.session.observe(action='fighting', now=self.clock())
                        self.session.note_fight(won)   # remembered against the resident
                    listener = self.on_fight
                    if listener is not None:
                        try:
                            listener(won)
                        except Exception as exc:
                            self._log(f"fight listener failed: {exc}")
            return consequence

        if kind == CONSEQUENCE_MATED:
            self._note_mated(detail.get('mating_id'))
            return consequence

        if kind == CONSEQUENCE_HIT:
            if detail.get('taken', True):
                self._feel_hit(squid, detail)
            elif self.session is not None and (not detail.get('peer_uuid')
                    or detail['peer_uuid'] == self.session.peer.uuid):
                self.session.note_hit(taken=False,
                                      what='poop' if detail.get('what') == 'poop' else 'rock')
            elif detail.get('peer_uuid'):
                memory = getattr(squid, 'memory_manager', None)
                if memory is not None:
                    memory.add_short_term_memory('social', 'rock:' + detail['throw_id'],
                        {'peer_uuid': detail['peer_uuid'], 'hits_given': 1}, importance=3)
            return consequence

        if kind == CONSEQUENCE_THROWN:
            memory = getattr(squid, 'memory_manager', None)
            if memory is not None:
                memory.add_short_term_memory('play', 'rock_throw', dict(detail), importance=2)
            track = getattr(self.logic, 'track_rock_thrown', None)
            if callable(track):
                track()
            return consequence

        # File the objective fact against this individual. What went into the
        # tank's ledger is what HAPPENED - an object changed hands, food was
        # eaten, an action found nothing - never a verdict about the resident.
        if self.session is not None:
            if kind == CONSEQUENCE_CONTEST:
                if detail.get('won'):
                    self.session.note_item_taken()
                self.session.observe(action='contesting', now=self.clock())
            elif kind == CONSEQUENCE_ATE and detail.get('ok'):
                self.session.observe(action='eating', now=self.clock())
        lifecycle = getattr(squid, 'lifecycle', None)
        can_eat = lifecycle is None or lifecycle.can_eat
        if kind == CONSEQUENCE_ATE and detail.get('ok') and can_eat:
            squid.hunger = max(0.0, float(getattr(squid, 'hunger', 50.0))
                               - _ATE_HUNGER_RELIEF)
        elif kind == CONSEQUENCE_CONTEST:
            if detail.get('won'):
                squid.satisfaction = min(100.0, float(getattr(squid, 'satisfaction', 50.0))
                                         + _CONTEST_WON_SATISFACTION)
            else:
                squid.anxiety = min(100.0, float(getattr(squid, 'anxiety', 50.0))
                                    + _CONTEST_LOST_ANXIETY)
        elif kind == CONSEQUENCE_BLOCKED:
            squid.satisfaction = max(0.0, float(getattr(squid, 'satisfaction', 50.0))
                                     - _BLOCKED_SATISFACTION)
        return consequence

    def _note_mated(self, mating_id) -> bool:
        """The host says this visit's contact was a mating.

        Only remembered. The egg is in the host's tank and the parent that
        starves for it is the host's resident; nothing in this squid's body
        or lifecycle changes, and no drive is nudged to say how it should feel.
        The host repeats the news, so it is filed once by its id: a mating
        already in this visit's record, or already in memory, is ignored.
        """
        from src.lifecycle import is_valid_mating_id
        if not is_valid_mating_id(mating_id):
            return False
        # Its half of the hatchling's weights, made here from its own brain.
        # Sent every time the news comes - the host keeps it once - so a
        # lost packet does not leave the egg with one parent: the host retells
        # a mating when the same squid comes back, and the gamete goes again
        # then too, though the mating itself is already remembered.
        self._send_gamete(mating_id)
        if self.peer_ledger is not None and self.peer_ledger.has_mated(mating_id):
            return False
        if self.session is None:
            self._open_session()
        if self.session is None:
            return False
        if self.session.note_mated(mating_id):
            self._log(f"Mating {mating_id} with {self.session.peer} noted")
            return True
        return False

    def _send_gamete(self, mating_id: str) -> bool:
        from src.inheritance import gamete
        from .remote_protocol import Gamete, MSG_GAMETE
        window = getattr(self.logic, 'brain_window', None)
        brain = getattr(window, 'brain_widget', None)
        if brain is None or not self.visit_id:
            return False
        if mating_id not in self._gametes:
            self._gametes[mating_id] = gamete(getattr(brain, 'weights', {}) or {})
        genes = self._gametes[mating_id]
        if not genes:
            return False
        return bool(self.send(MSG_GAMETE, Gamete(self.visit_id, mating_id, genes).to_payload()))

    # ==================================================================
    # The visit
    # ==================================================================
    def begin_visit(self, host_identity: Optional[SquidIdentity],
                    visit_id: str = '') -> str:
        squid = getattr(self.logic, 'squid', None)
        local_uuid = str(getattr(squid, 'uuid', '')) if squid else ''
        self.host_uuid = host_identity.uuid if host_identity else ''
        # Left empty unless the caller already knows it: the host names the
        # visit and the first frame carries the name.
        self.visit_id = visit_id
        self.perception.begin(self.visit_id)
        self.consequences = []
        self._seq = 0
        from src.decision_engine import wants
        self._inking = wants('act_ink', float(self._brain_state().get('act_ink', 0.) or 0.))
        self._resisting_sleep = False
        if squid is not None:
            squid.is_transitioning = True
            squid.can_move = False
            # Its body is in the host's tank, not this one: hidden here until
            # end_visit. Whose tank, the first frame says (_open_session).
            if getattr(squid, 'squid_item', None) is not None:
                try:
                    squid.squid_item.setVisible(False)
                except Exception:
                    pass
        return self.visit_id

    def go_home(self, action: str) -> None:
        """Come home because its own network chose to (HOMEWARD), and say why."""
        from src.social_knowledge import think
        think(self.logic, HOMEWARD[action])
        self._log(f"going home: {action} won")
        self.end_visit(reason=END_DEPARTED, notify=True)

    def end_visit(self, reason: str = END_DEPARTED, notify: bool = True) -> None:
        """Come home. Always safe to call, and always leaves the squid usable.

        This is the one function that must never fail to restore the squid,
        because every failure path in the round trip ends here: a host that
        stopped talking, a visit the host ended, a plugin being disabled.
        """
        if notify and self.visit_id:
            try:
                self.send('visit_end',
                          VisitEnd(self.visit_id, reason).to_payload())
            except Exception as exc:
                self._log(f"could not announce departure: {exc}")
        self.close_session()
        self.perception.end()
        self._perceive_host_tank(away=False)   # home again: its own senses take over
        self.visit_id = ''
        self.host_uuid = ''
        self.last_intent = None
        squid = getattr(self.logic, 'squid', None)
        if squid is not None:
            squid.is_transitioning = False
            squid.can_move = True
            if getattr(squid, 'squid_item', None) is not None:
                try:
                    squid.squid_item.setVisible(True)
                except Exception:
                    pass

    def close_session(self) -> Optional[Any]:
        """Turn the visit into a memory of that individual.

        Written through PeerLedger, which writes through the squid's own
        MemoryManager - so a visit becomes an ordinary memory, promoted by the
        ordinary rule, readable by the Memory tab, and keyed to the resident
        so it can never colour an encounter with anyone else.

        Returns the record, or None if nothing worth remembering happened.
        """
        session, self.session = self.session, None
        if session is None or self.peer_ledger is None:
            return None
        if not session.is_memorable(self.clock()):
            self._log(f"Visit to {session.peer} too brief to remember.")
            return None
        record = session.close(
            drives=drive_snapshot(getattr(self.logic, 'squid', None)),
            now=self.clock(),
            related_neurons=self._active_social_neurons())
        if self.peer_ledger.record(record):
            self._log(f"Visit remembered: {record.describe()}")
            self._learn_from(record)
            return record
        return None

    def _learn_from(self, record) -> None:
        """How the visit went moves how this squid meets ANY squid
        (src/social_learning.py), recorded on each synapse it moves."""
        from src.social_learning import learn_from_encounter
        window = getattr(self.logic, 'brain_window', None)
        brain = getattr(window, 'brain_widget', None)
        if brain is not None and hasattr(brain, 'apply_weight_change'):
            learn_from_encounter(brain, record.valence, record.outcome, record.peer.name)

    #: What a rock strike does to the body: a knock.
    HIT_HEALTH_COST = 2.0

    def _feel_hit(self, squid, detail=None) -> None:
        """Struck by something thrown in the host's tank - a rock (a knock and
        a startle) or poop (no harm, but anxiety up and happiness down: see
        throwing.HIT_EFFECTS). Felt, at home. Nothing says whether it was play
        or an attack; the squid's own network decides what to make of it."""
        from src.throwing import feel_hit
        detail = detail or {}
        what = 'poop' if detail.get('what') == 'poop' else 'rock'

        def startle(source):
            hook = getattr(self.logic, 'startle_squid', None)
            if callable(hook):
                try:
                    hook(source=source)
                except Exception as exc:
                    self._log(f"could not startle on a hit: {exc}")
        felt = feel_hit(squid, what, startle=startle)
        peer_uuid = detail.get('peer_uuid')
        if self.session is not None and (not peer_uuid or peer_uuid == self.session.peer.uuid):
            self.session.note_hit(taken=True, what=what)
        elif peer_uuid:
            memory = getattr(squid, 'memory_manager', None)
            if memory is not None:
                memory.add_short_term_memory('social', f"{what}:{detail['throw_id']}",
                    dict({'peer_uuid': peer_uuid, 'hits_taken': 1, 'what': what}, **felt),
                    importance=3)

    def _live_through_fight(self, squid, fight_id: str, won: bool,
                            detail: Dict[str, Any]) -> Dict[str, Any]:
        """What a fight the host resolved does to this squid, at home.

        Its body and drives take the outcome (src/fighting.py CONSEQUENCES),
        its aggression neuron is marked for good (fighting.scar), and the
        fight is filed in its long-term memory with everything behind it:
        whether it started it, the aggression or defence it fought with and
        its fitness (what its intent carried), both abilities and its chance.
        """
        from src import fighting
        from .encounter import remember_fight
        intent = self.last_intent
        started = bool(detail.get('you_started'))
        commit = getattr(intent, 'aggression' if started else 'defence', 0.0) if intent else 0.0
        mine = {'role': 'attacker' if started else 'defender',
                'fitness': getattr(intent, 'fitness', 1.0) if intent else 1.0,
                'commitment': round(float(commit or 0.0), 1),
                'committed_by': 'aggression' if started else 'defence',
                'ability': float(detail.get('your_ability', 0.0) or 0.0)}
        theirs = {'role': 'defender' if started else 'attacker',
                  'ability': float(detail.get('their_ability', 0.0) or 0.0)}
        resident = self.perception.resident
        record = {'first_won': bool(won), 'first_chance': float(detail.get('chance', .5) or .5),
                  'first': mine, 'second': theirs, 'fight_id': fight_id,
                  'opponent': getattr(resident, 'name', 'the resident'),
                  'opponent_uuid': getattr(resident, 'uuid', ''),
                  'why': {'aggression': mine['commitment']} if started else {},
                  'consequences': fighting.apply_consequences(squid, won)}
        window = getattr(self.logic, 'brain_window', None)
        brain = getattr(window, 'brain_widget', None)
        from src.social_knowledge import fight_thoughts, think
        for thought in fight_thoughts(record, 'first'):
            think(self.logic, thought)
        if brain is not None:
            record['aggression_rose'] = fighting.scar(
                brain, won, f"{'won' if won else 'lost'} a fight with {record['opponent']}")
        remember_fight(getattr(squid, 'memory_manager', None), record, me='first')
        return record

    def _active_social_neurons(self) -> List[str]:
        """The social senses and neurons it grew, if active during this.

        Stored on the memory as related_neurons, so the record points at the
        structure that was involved in having the experience.
        """
        from .encounter import active_social_neurons
        window = getattr(self.logic, 'brain_window', None)
        return active_social_neurons(getattr(window, 'brain_widget', None))

    def tick(self) -> Optional[ActionIntent]:
        """One behavioural cadence. Returns the intent sent, if any.

        Also the place a lost host is noticed. A visiting squid whose host has
        gone quiet comes HOME rather than waiting - the alternative is a squid
        that is neither in its own tank nor in anyone else's, which is the
        stuck state this stage has to make impossible.
        """
        if not self.perception.away:
            return None
        # A squid away from home always comes home to sleep, however it
        # came to be asleep - it never sleeps in another squid's tank.
        if getattr(getattr(self.logic, 'squid', None), 'is_sleeping', False):
            self.go_home('act_rest')
            return None
        if not self.perception.linked:
            silence = self.clock() - self.perception.received_at
            if silence >= LINK_TIMEOUT:
                self._log(f"host silent for {silence:.1f}s - coming home")
                self.end_visit(reason=END_LINK_LOST, notify=True)
            return None
        intent = self.decide()
        # Ink is a parallel reflex, not a rival in the action competition.
        # Transmit one firing; the host draws it without consulting a brain.
        from src.decision_engine import wants
        activation = float(self._brain_state().get('act_ink', 0.) or 0.)
        firing = wants('act_ink', activation)
        if firing and not self._inking:
            self._seq += 1
            self.send('action_intent', ActionIntent(self.visit_id, 'act_ink',
                seq=self._seq, sent_at=self.clock(), activation=activation).to_payload())
            track = getattr(self.logic, 'track_visitor_ink', None)
            if callable(track):
                track()
        self._inking = firing
        return intent

    def on_visit_end(self, payload: Dict[str, Any]) -> bool:
        """The host ended it."""
        try:
            ending = VisitEnd.from_payload(payload)
        except ProtocolError:
            return False
        if ending.visit_id != self.visit_id:
            return False
        self.end_visit(reason=ending.reason, notify=False)
        return True

    # ==================================================================
    def _brain_state(self) -> Dict[str, float]:
        window = getattr(self.logic, 'brain_window', None)
        widget = getattr(window, 'brain_widget', None)
        return dict(getattr(widget, 'state', {}) or {})

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.info(f"[VisitorMind] {message}")


__all__ = ['VisitorMind', 'RemotePerception', 'REMOTE_DRIVEN_SENSORS', 'HOMEWARD']
