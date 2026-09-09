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

from .identity import SquidIdentity
from .remote_protocol import (
    ActionIntent, Consequence, PerceptionFrame, ProtocolError, VisitEnd,
    CONSEQUENCE_ATE, CONSEQUENCE_BLOCKED, CONSEQUENCE_CONTEST,
    CONSEQUENCE_EJECTED, END_DEPARTED, END_LINK_LOST, HEADINGS,
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
        self._seq = 0
        self._restore: Dict[str, Callable] = {}

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
        return accepted

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

        self.consequences.append(consequence)
        squid = getattr(self.logic, 'squid', None)
        if squid is None:
            return consequence

        kind, detail = consequence.kind, consequence.detail
        if kind == CONSEQUENCE_ATE and detail.get('ok'):
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
        if squid is not None:
            squid.is_transitioning = True
            squid.can_move = False
        return self.visit_id

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
        self.perception.end()
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

    def tick(self) -> Optional[ActionIntent]:
        """One behavioural cadence. Returns the intent sent, if any.

        Also the place a lost host is noticed. A visiting squid whose host has
        gone quiet comes HOME rather than waiting - the alternative is a squid
        that is neither in its own tank nor in anyone else's, which is the
        stuck state this stage has to make impossible.
        """
        if not self.perception.away:
            return None
        if not self.perception.linked:
            silence = self.clock() - self.perception.received_at
            if silence >= LINK_TIMEOUT:
                self._log(f"host silent for {silence:.1f}s - coming home")
                self.end_visit(reason=END_LINK_LOST, notify=True)
            return None
        return self.decide()

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
    def recalled_sensors(self) -> Dict[str, float]:
        """This squid's own memory of the resident it is looking at.

        Computed HERE, never received. The host has no access to this squid's
        PeerLedger and could not compute these if it wanted to, which is why
        the protocol refuses to carry them: an encounter is coloured by what
        this squid remembers, and only this machine knows that.
        """
        blank = {'conspecific_familiarity': 0.0,
                 'conspecific_recalled_good': 0.0,
                 'conspecific_recalled_bad': 0.0}
        if not self.perception.linked or self.peer_ledger is None:
            return blank
        uuid = self.perception.resident_uuid()
        if not uuid:
            return blank
        return {
            'conspecific_familiarity': self.peer_ledger.familiarity(uuid),
            'conspecific_recalled_good': self.peer_ledger.recalled_good(uuid),
            'conspecific_recalled_bad': self.peer_ledger.recalled_bad(uuid),
        }

    def _brain_state(self) -> Dict[str, float]:
        window = getattr(self.logic, 'brain_window', None)
        widget = getattr(window, 'brain_widget', None)
        return dict(getattr(widget, 'state', {}) or {})

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.info(f"[VisitorMind] {message}")


__all__ = ['VisitorMind', 'RemotePerception', 'REMOTE_DRIVEN_SENSORS']
