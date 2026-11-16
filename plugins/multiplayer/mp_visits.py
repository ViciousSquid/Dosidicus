"""A visit, message by message: the remote-mind round trip between a host
tank and a visitor's home, and what each side perceives of the other.

See docs/protocol.md.
"""
import time
import math
from typing import Dict, List, Any
from . import mp_constants # Access constants like mp_constants.PLUGIN_NAME
from src.vision_cone import VIEW_CONE_ANGLE, in_view_cone
from .identity import SquidIdentity
from .peer_ledger import PeerLedger
from .encounter import (EncounterSession, drive_snapshot, active_social_neurons,
                        perceive_recognition)
from .host_body import HostBody, DEFAULT_MATING_CHANCE, DEFAULT_MATING_CONTACT_SECONDS
from .visitor_mind import VisitorMind
from .remote_protocol import (
    ActionIntent, ProtocolError, VisitEnd,
    END_EJECTED, ROUND_TRIP_INTERVAL,
)


class VisitProtocolMixin:
    """Part of MultiplayerPlugin (see mp_plugin_logic.py); not used on its own."""

    # =====================================================================
    # ENCOUNTERS
    # =====================================================================

    def install_encounter_sensors(self) -> bool:
        """Set up encounters, for this squid as host and as visitor.

        No sense organ is added to the brain for another squid: the squid sees
        one with its ordinary vision, and the neurons that stand for other
        squid are the ones neurogenesis grows when they first matter
        (brain_constants.SOCIAL_SENSORS, SOCIAL_NEURONS). What this does
        register is where the squid's EXISTING senses point while it is away.
        """
        if not self.tamagotchi_logic or not self.plugin_manager:
            return False
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        self.local_identity = SquidIdentity.from_squid(squid)

        memory_manager = getattr(squid, 'memory_manager', None)
        self.peer_ledger = PeerLedger(memory_manager)

        # This squid's brain, for when its body is in someone else's tank.
        self.visitor_mind = VisitorMind(
            tamagotchi_logic=self.tamagotchi_logic,
            peer_ledger=self.peer_ledger,
            send=self._send, logger=self.logger)
        self.visitor_mind.on_fight = self.announce_fight
        # This tank, for when it is hosting someone else's squid. It is the
        # authority on matings in this tank and records them through the
        # core lifecycle before the visitor is told.
        lifecycle_config = getattr(self.tamagotchi_logic, 'lifecycle_config', None) or {}
        self.host_body = HostBody(
            tamagotchi_logic=self.tamagotchi_logic,
            conspecific_view=self.conspecific_view,
            logger=self.logger,
            mating_chance=lifecycle_config.get('mating_chance', DEFAULT_MATING_CHANCE),
            mating_contact_seconds=lifecycle_config.get(
                'mating_contact_seconds', DEFAULT_MATING_CONTACT_SECONDS),
            on_mating=self.record_mating)
        # One fight cloud when a contest breaks out between two squid here.
        self.conspecific_view.on_contest = self.show_fight_cloud

        # Published the way latest_vision_result is, so the engine's own
        # actuator can consult it through getattr and run without it.
        self.tamagotchi_logic.conspecific_view = self.conspecific_view

        registered = []

        # While the squid is away, three of its BUILT-IN senses report the
        # host tank instead of this one. Registered as plugin handlers, which
        # take precedence in BrainNeuronHooks, and each wraps the original so
        # the squid keeps one set of sense organs for its whole life - they
        # simply point somewhere else for the duration of a visit.
        try:
            from src.brain_neuron_hooks import BrainNeuronHooks
        except ImportError:
            from brain_neuron_hooks import BrainNeuronHooks
        builtin = BrainNeuronHooks(self.tamagotchi_logic).handlers
        for name, handler in self.visitor_mind.sensor_overrides(builtin).items():
            self.plugin_manager.register_neuron_handler(
                neuron_name=name, handler=handler,
                plugin_name=mp_constants.PLUGIN_NAME,
                metadata={'description': f'{name} (host tank while visiting)',
                          'category': 'visiting', 'source': 'plugin'})
            registered.append(name)

        self.logger.info(f"Senses that point at the host tank while visiting: {', '.join(registered)}")
        return True

    # ------------------------------------------------------------------
    # The remote-mind round trip
    # ------------------------------------------------------------------
    def _send(self, message_type: str, payload: Dict) -> bool:
        """One place messages leave this instance, so failure is one shape."""
        if not self.network_node:
            return False
        try:
            return bool(self.network_node.send_message(message_type, payload))
        except Exception as exc:
            self.logger.error(f"Could not send {message_type}: {exc}")
            return False

    def run_round_trip(self) -> None:
        """One behavioural cadence, for both roles this instance plays.

        As a HOST: tell each visitor what it can see, and report anything that
        happened to it. As a VISITOR: ask this squid's own brain what it wants
        and post that to whoever is hosting it.

        Runs on ROUND_TRIP_INTERVAL, which is the agreed cadence rather than
        the sync interval, so behaviour and rendering can be paced separately.
        """
        now = time.time()
        if now - self._last_round_trip < ROUND_TRIP_INTERVAL:
            return
        self._last_round_trip = now

        if self.host_body is not None:
            for actor, reason in self.host_body.tick():
                self.end_visit_as_host(actor, reason)
            for actor in list(self.host_body.visitors.values()):
                node_id = self.visit_node_ids.get(actor.uuid)
                if node_id and self.entity_manager is not None:
                    self.entity_manager.follow_body(node_id, actor.x, actor.y, actor.facing)
                self._send('perception_frame',
                           self.host_body.build_frame(actor).to_payload())
                for consequence in self.host_body.drain_consequences(actor):
                    self._send('consequence', consequence.to_payload())
            # Both squid show that they have noticed each other. The
            # resident's own icon comes from process_squid_detection; this is
            # the visitor's, drawn above its body here because its real squid
            # is hidden at home for the duration of the visit.
            for actor in self.host_body.drain_first_sightings():
                node_id = self.visit_node_ids.get(actor.uuid)
                if node_id and self.entity_manager:
                    self.entity_manager.show_notice_icon(node_id)

        if self.visitor_mind is not None:
            self.visitor_mind.tick()

    def handle_visit_response(self, node, message: Dict, addr) -> bool:
        """The host has answered this squid's arrival.

        Accepted, the squid's brain switches its senses to the host's frames.
        Refused, it comes straight back - the alternative is a squid that has
        left its own tank and been let into nobody else's.
        """
        if self.visitor_mind is None:
            return False
        payload = message.get('payload') or {}
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        mine = self.network_node is not None and payload.get('to') == self.network_node.node_id
        if squid is None or not (payload.get('peer_uuid') == str(getattr(squid, 'uuid', ''))
                                 or (mine and not payload.get('accepted'))):
            return False          # somebody else's answer
        if self._asked_to_visit and message.get('node_id') != self._asked_to_visit:
            return False          # a tank it did not ask to visit

        if payload.get('accepted'):
            host_identity = self.peer_identities.get(message.get('node_id'))
            self.visitor_mind.begin_visit(host_identity)
            self.logger.info("Entry accepted; awaiting perception from the host.")
            return True

        self.logger.info(f"Entry refused ({payload.get('reason')}); coming home.")
        self.visitor_mind.end_visit(reason='departed', notify=False)
        return True

    def _from_my_host(self, message: Dict) -> bool:
        """Did this come from the one tank this squid asked to visit?

        Visit ids travel in the open, so without this a visitor would adopt
        the first frame any host sent - another squid's visit included.
        """
        return not self._asked_to_visit or message.get('node_id') == self._asked_to_visit

    def _from_visitor(self, actor, message: Dict) -> bool:
        """Did this come from the node this visitor arrived from?"""
        node = self.visit_node_ids.get(actor.uuid)
        return not node or message.get('node_id') == node

    def handle_perception_frame(self, node, message: Dict, addr) -> bool:
        """A host is telling this squid what it can see over there."""
        if self.visitor_mind is None or not self._from_my_host(message):
            return False
        return self.visitor_mind.on_perception_frame(message.get('payload') or {})

    def handle_action_intent(self, node, message: Dict, addr) -> bool:
        """A visiting squid's brain has decided something. Carry it out.

        Validated, then dispatched. This instance never works out what the
        visitor should do - it does not have the visitor's brain, drives or
        memory and cannot ask for them.
        """
        if self.host_body is None:
            return False
        payload = message.get('payload') or {}
        try:
            intent = ActionIntent.from_payload(payload)
        except ProtocolError as exc:
            self.logger.warning(f"Rejected an action intent: {exc}")
            return False
        for actor in self.host_body.visitors.values():
            if actor.visit_id == intent.visit_id:
                if not self._from_visitor(actor, message):
                    return False
                return self.host_body.apply_intent(actor, intent)
        return False

    def handle_consequence(self, node, message: Dict, addr) -> bool:
        """The host is reporting what actually happened to this squid."""
        if self.visitor_mind is None or not self._from_my_host(message):
            return False
        return self.visitor_mind.on_consequence(
            message.get('payload') or {}) is not None

    def handle_visit_end(self, node, message: Dict, addr) -> bool:
        """Either side has ended a visit."""
        payload = message.get('payload') or {}
        handled = False
        if self.visitor_mind is not None and self._from_my_host(message):
            handled = self.visitor_mind.on_visit_end(payload)
        if not handled and self.host_body is not None:
            try:
                ending = VisitEnd.from_payload(payload)
            except ProtocolError:
                return False
            for actor in list(self.host_body.visitors.values()):
                if actor.visit_id == ending.visit_id and self._from_visitor(actor, message):
                    self.end_visit_as_host(actor, ending.reason, notify=False)
                    return True
        return handled

    def end_visit_as_host(self, actor, reason: str = END_EJECTED,
                          notify: bool = True) -> None:
        """Take a visitor's body out of this tank, and say so."""
        if self.host_body is None:
            return
        # Whatever happened to it last - an 'ejected' for a silent link, a
        # hit - goes out before its body does; it was being dropped.
        for consequence in self.host_body.drain_consequences(actor):
            self._send('consequence', consequence.to_payload())
        if notify:
            self._send('visit_end',
                       VisitEnd(actor.visit_id, reason).to_payload())
        self.host_body.remove(actor.uuid)
        self.visit_node_ids.pop(actor.uuid, None)
        node_id = next((n for n, i in self.peer_identities.items()
                        if i and i.uuid == actor.uuid), None)
        if node_id and self.entity_manager:
            try:
                self.entity_manager.remove_remote_squid(node_id)
            except Exception as exc:
                self.logger.error(f"Could not remove a departed visitor: {exc}")
        self.close_encounter(actor.uuid)
        self.logger.info(f"Visit by {actor.identity} ended: {reason}")

    def _resident_is_away(self) -> bool:
        """Is this tank's own squid out visiting another tank?"""
        mind = getattr(self, 'visitor_mind', None)
        return bool(mind is not None and getattr(mind.perception, 'away', False))

    def update_encounters(self) -> None:
        """Open, feed and close encounters. Called on the sync tick.

        This does not decide anything. It notices that another squid is
        present, records what this squid did while it was, and writes down how
        the drives moved - which is the evidence the existing learning systems
        already work from.
        """
        if not self.tamagotchi_logic or self.peer_ledger is None:
            return
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        if squid is None:
            return

        now = time.time()
        self.conspecific_view.prune(now)
        drives = drive_snapshot(squid)
        action = getattr(squid, 'status', '') or ''

        # Anything the actuator did since the last tick belongs to whichever
        # encounter is open with that peer.
        for contest in self.conspecific_view.drain_contests():
            session = self.open_encounters.get(contest.get('peer_uuid', ''))
            if session is None or not contest.get('taken'):
                continue
            # Which way the object went is the whole difference between a good
            # encounter and a bad one, and it is an objective fact about the
            # tank rather than an interpretation of it.
            if contest.get('by') == 'peer':
                session.note_item_lost()
            else:
                session.note_item_taken()

        # A squid that is out visiting is not in its own tank. Whoever is in
        # that tank is not with it, and nothing that happens there is its
        # experience: it opens no encounter, and one it was in ended when it
        # swam out. (It used to go on "meeting" a visitor to its empty tank,
        # and came to remember an encounter with a squid it had never seen.)
        away = self._resident_is_away()
        present = {}
        for presence in self.conspecific_view.presences.values():
            if away or now - presence.last_update > 3.0:
                continue
            present[presence.uuid] = presence
        if away:
            for uuid_key in list(self.open_encounters):
                self.close_encounter(uuid_key, drives, now)

        self._perceive_visitors(squid, present)

        for uuid_key, presence in present.items():
            session = self.open_encounters.get(uuid_key)
            if session is None:
                summary = self.peer_ledger.summary(uuid_key)
                session = EncounterSession(
                    presence.identity, drives,
                    first_meeting=(summary.encounters == 0), now=now)
                self.open_encounters[uuid_key] = session
                self.logger.info(
                    f"Encounter opened with {presence.identity} "
                    f"(first meeting: {session.first_meeting})")
            proximity = max(0.0, 100.0 - presence.distance / 4.0)
            session.observe(drives=drives, action=action,
                            peer_action=presence.status,
                            proximity=proximity, visible=True, now=now)

        for uuid_key, session in list(self.open_encounters.items()):
            if not session.should_close(now):
                continue
            # Closed on its own terms, which includes a visitor that has been
            # here longer than MAX_ENCOUNTER_DURATION. A peer that is STILL
            # present simply starts a fresh encounter on the next tick, so a
            # squid that shares its tank for an hour accumulates experiences
            # rather than one enormous unwritten one.
            self.close_encounter(uuid_key, drives, now)

    def visit_destination(self, now: float | None = None) -> str:
        """The aquarium a squid venturing out asks to visit: the one heard
        most recently, if any was heard within venturing.HEARD_WITHIN."""
        from src.venturing import HEARD_WITHIN
        now = time.time() if now is None else now
        heard = {node: at for node, at in self._peers_last_heard.items()
                 if now - at <= HEARD_WITHIN}
        return max(heard, key=heard.get) if heard else ''

    def address_exit(self, exit_data: Dict[str, Any]) -> bool:
        """Address a departure to one host (exit_data['to']).

        A squid_exit is multicast, and every host used to admit whatever it
        heard: with three tanks or more, one squid got a body in two of them.
        Now only the host it names takes it in, and only that host's answer is
        taken (handle_visit_response). False when no aquarium is nearby.
        """
        destination = self.visit_destination()
        if not destination:
            return False
        exit_data['to'] = destination
        self._asked_to_visit = destination
        return True

    def _perceive_aquariums(self, now: float | None = None) -> None:
        """Whether another aquarium is nearby: a peer heard on the network
        lately (src/venturing.py). The first time, the squid grows the sense
        for it (aquarium_nearby); whether it then ventures out is its own."""
        from src.venturing import peer_heard
        brain = getattr(getattr(self.tamagotchi_logic, 'brain_window', None),
                        'brain_widget', None)
        if hasattr(brain, 'perceive'):
            brain.perceive('aquarium_heard',
                           peer_heard(self._peers_last_heard,
                                      time.time() if now is None else now))

    def _perceive_visitors(self, squid, present) -> None:
        """What the resident's own senses make of the squid in its tank.

        Whether it sees one, and how close, is its vision's (TamagotchiLogic).
        Who it is looking at - the nearest visitor in its view cone - and
        what it remembers of that individual comes from here, from its own
        memory; so does feeling a scuffle it is in.
        """
        brain = getattr(getattr(self.tamagotchi_logic, 'brain_window', None),
                        'brain_widget', None)
        if not hasattr(brain, 'perceive'):
            return
        looked_at = ''
        if not getattr(squid, 'is_transitioning', False) and present:
            half_w = float(getattr(squid, 'squid_width', 0.0)) / 2
            half_h = float(getattr(squid, 'squid_height', 0.0)) / 2
            cx = float(getattr(squid, 'squid_x', 0.0)) + half_w
            cy = float(getattr(squid, 'squid_y', 0.0)) + half_h
            angle = float(getattr(squid, 'current_view_angle', 0.0))
            ui = getattr(self.tamagotchi_logic, 'user_interface', None)
            reach = math.hypot(float(getattr(ui, 'window_width', 1280)),
                               float(getattr(ui, 'window_height', 900)))
            in_view = [p for p in present.values()
                       if in_view_cone(cx, cy, angle, VIEW_CONE_ANGLE, reach,
                                       p.x + half_w, p.y + half_h)]
            if in_view:
                looked_at = min(in_view, key=lambda p: math.hypot(
                    p.x + half_w - cx, p.y + half_h - cy)).uuid
        perceive_recognition(brain, self.peer_ledger, looked_at)
        clock = self.host_body.clock() if self.host_body is not None else time.time()
        fighting = self.host_body is not None and any(
            clock < actor.body_busy_until for actor in self.host_body.visitors.values())
        brain.perceive('in_fight', 100.0 if fighting else 0.0)

    def close_encounter(self, peer_uuid: str, drives: Dict[str, float] | None = None,
                        now: float | None = None) -> None:
        """Finish an encounter and file it as an experience."""
        session = self.open_encounters.pop(peer_uuid, None)
        if session is None:
            return
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        if drives is None:
            drives = drive_snapshot(squid)
        if not session.is_memorable(now):
            self.logger.debug(f"Encounter with {session.peer} too brief to remember.")
            return
        record = session.close(drives=drives, now=now,
                               related_neurons=list(self._active_encounter_neurons()))
        if self.peer_ledger.record(record):
            self.logger.info(f"Encounter remembered: {record.describe()}")
            self.peer_ledger.count_first_meeting(getattr(squid, 'statistics', None))
            # How it went moves how the squid meets ANY squid, strangers too
            # (src/social_learning.py), recorded on each synapse it moves.
            from src.social_learning import learn_from_encounter
            brain = getattr(getattr(self.tamagotchi_logic, 'brain_window', None),
                            'brain_widget', None)
            if brain is not None and hasattr(brain, 'apply_weight_change'):
                learn_from_encounter(brain, record.valence, record.outcome, record.peer.name)
            if hasattr(self.tamagotchi_logic, 'show_message'):
                self.tamagotchi_logic.show_message(
                    f"Your squid remembers a {record.outcome} encounter with {record.peer.name}.")

    def perceive_remote_squid(self, remote_node_id: str, squid_data: Dict) -> bool:
        """Tell the local squid's senses where another squid is.

        Position only, plus who it is and what it is visibly doing. Nothing
        about the other squid's brain crosses this line, because nothing about
        it needs to: the local squid can see a squid, not its intentions.
        """
        if not squid_data or self.peer_ledger is None:
            return False
        local_squid = getattr(self.tamagotchi_logic, 'squid', None)
        if local_squid is None:
            return False

        identity = self.peer_identities.get(remote_node_id)
        if identity is None:
            identity = SquidIdentity.from_payload(squid_data.get('identity') or {})
            if identity is None:
                # No usable identity: still perceptible as A squid, but not
                # recognisable as a PARTICULAR one, so it gets a per-node
                # stand-in that will never match a remembered individual.
                return False
            self.peer_identities[remote_node_id] = identity

        try:
            peer_x = float(squid_data.get('x', 0.0))
            peer_y = float(squid_data.get('y', 0.0))
        except (TypeError, ValueError):
            return False

        self.conspecific_view.observe_peer(
            identity,
            x=peer_x, y=peer_y,
            observer_x=getattr(local_squid, 'squid_x', 0.0),
            observer_y=getattr(local_squid, 'squid_y', 0.0),
            facing=getattr(local_squid, 'squid_direction', 'right'),
            status=str(squid_data.get('status', ''))[:32],
        )
        return True

    def _active_encounter_neurons(self) -> List[str]:
        """The neurons involved in having this encounter, if they were active.

        Stored on the memory as related_neurons, which the Memory tab already
        knows how to show, so an encounter memory can point at the structure
        that was involved in having it: the social senses and neurons the
        squid grew.
        """
        brain_window = getattr(self.tamagotchi_logic, 'brain_window', None)
        return active_social_neurons(getattr(brain_window, 'brain_widget', None))
