"""What two squid in one tank do to each other: rocks that land, fights and
mating (docs/fights.md, docs/rocks.md, docs/reproduction.md).
"""
import uuid
import time
import math
from typing import Dict
from src import fighting
from src.social_knowledge import fight_thoughts, think
from .remote_protocol import CONSEQUENCE_FIGHT, CONSEQUENCE_HIT
from .identity import SquidIdentity
from .encounter import (EncounterSession, drive_snapshot, remember_fight)
from .remote_protocol import (
    ProtocolError, END_EJECTED,
)


class FightsAndMatingMixin:
    """Part of MultiplayerPlugin (see mp_plugin_logic.py); not used on its own."""

    # ------------------------------------------------------------------
    # Reproduction, and what a resident's death means for visits
    # ------------------------------------------------------------------
    def record_mating(self, actor, mating_id: str) -> bool:
        """HostBody has resolved a mating with this tank's resident.

        Recorded in the core lifecycle - which lays the egg and saves, as one
        record - and only then in the encounter. HostBody tells the visitor
        afterwards, and only if this returned True, so the visitor can never
        hear about a mating this tank did not keep.
        """
        logic = self.tamagotchi_logic
        if logic is None or not hasattr(logic, 'record_reproduction'):
            return False
        if not logic.record_reproduction(mating_id, actor.identity.uuid,
                                         actor.identity.name):
            return False
        session = self.open_encounters.get(actor.uuid)
        if session is None:
            squid = getattr(logic, 'squid', None)
            summary = self.peer_ledger.summary(actor.uuid) if self.peer_ledger else None
            session = EncounterSession(
                actor.identity, drive_snapshot(squid),
                first_meeting=(summary is None or summary.encounters == 0))
            self.open_encounters[actor.uuid] = session
        session.note_mated(mating_id)
        self.logger.info(f"Mating {mating_id} with {actor.identity} recorded")
        try:
            self.show_mating_heart(actor)
        except Exception as exc:
            self.logger.error(f"Could not draw the mating heart: {exc}")
        return True

    def handle_rock_hit(self, target_uuid='', throw=None, **_kw) -> bool:
        """Route a physical impact to the body that lives on each peer."""
        if self.host_body is None:
            return False
        throw = throw or {}
        throw_id = throw.get('throw_id')
        if not isinstance(throw_id, str) or not throw_id:
            return False
        resident = self.tamagotchi_logic.squid
        source_uuid = throw.get('source_uuid', str(resident.uuid))
        target = self.host_body.visitor(target_uuid)
        source = self.host_body.visitor(source_uuid)
        identity = source.identity if source else SquidIdentity.from_payload(throw.get('source_identity') or {})
        if target is None and (target_uuid != str(resident.uuid)
                or identity is None or identity.uuid != source_uuid):
            return False
        hits = getattr(self, '_reported_rock_hits', None)
        if hits is None:
            self._reported_rock_hits = hits = set()
        key = (throw_id, target_uuid)
        if key in hits:
            return False
        hits.add(key)
        what = 'poop' if throw.get('what') == 'poop' else 'rock'
        fact = {'what': what, 'speed': round(float(throw.get('speed', 0.) or 0.), 1),
                'throw_id': throw_id}
        if target is not None:
            self.host_body._report(target, CONSEQUENCE_HIT,
                                   dict(fact, taken=True, peer_uuid=source_uuid))
        else:
            feel = getattr(self.tamagotchi_logic, 'feel_rock_hit', None)
            if callable(feel):
                feel(throw)  # the core hook may already have delivered it
            else:
                from src.throwing import feel_hit
                feel_hit(resident, what, startle=lambda source:
                         self.tamagotchi_logic.startle_squid(source=source))
        if source is not None:
            self.host_body._report(source, CONSEQUENCE_HIT,
                                   dict(fact, taken=False, peer_uuid=target_uuid))
        # Only the resident's OWN encounter is recorded here. A visitor
        # records its experience at home, never in a surrogate host brain.
        peer = source if target is None else (target if source_uuid == str(resident.uuid) else None)
        if peer is not None:
            session = self.open_encounters.get(peer.uuid)
            if session is None:
                session = EncounterSession(peer.identity, drive_snapshot(resident))
                self.open_encounters[peer.uuid] = session
            session.note_hit(taken=target is None, what=what)
        elif target is None and identity is not None:
            # A rock remains physical after its thrower has left. Keep this
            # later impact against its source; do not resurrect a visit.
            session = EncounterSession(identity, drive_snapshot(resident))
            session.note_hit(taken=True, what=what)
            record = session.close(drives=drive_snapshot(resident))
            if self.peer_ledger is not None:
                self.peer_ledger.record(record)
        return True

    def handle_gamete(self, node=None, message=None, addr=None, **_kw) -> bool:
        """A visitor has sent its half of the hatchling's weights.

        Kept only for this tank's own egg, from that very mating, from the
        squid this resident mated with - and once (Lifecycle.add_genes).
        """
        from .remote_protocol import Gamete
        payload = (message or {}).get('payload') if isinstance(message, dict) else None
        try:
            gamete = Gamete.from_payload(payload)
        except ProtocolError as exc:
            self.logger.warning(f"Rejected a gamete: {exc}")
            return False
        actor = next((a for a in (self.host_body.visitors.values() if self.host_body else [])
                      if a.visit_id == gamete.visit_id), None)
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        lifecycle = getattr(squid, 'lifecycle', None)
        if actor is None or lifecycle is None or lifecycle.mating_id != gamete.mating_id \
                or lifecycle.mate_uuid != actor.uuid or not self._from_visitor(actor, message or {}):
            return False
        keep = getattr(self.tamagotchi_logic, 'add_mate_genes', None)
        if not callable(keep) or not keep(gamete.mating_id, actor.identity.name, gamete.genes):
            return False
        self.logger.info(f"Kept {actor.identity}'s half of the egg's weights "
                         f"({len(gamete.genes)} synapses)")
        return True

    def show_mating_heart(self, actor) -> bool:
        """A mating here: draw ONE beating heart over the pair.

        Called once the mating is recorded, so the heart only ever marks a
        mating this tank kept. A drawing and nothing else, like the fight
        cloud.
        """
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        show = getattr(self.entity_manager, 'show_mating_heart', None)
        if squid is None or not callable(show):
            return False
        width = float(getattr(squid, 'squid_width', 0.0))
        height = float(getattr(squid, 'squid_height', 0.0))
        rx = float(getattr(squid, 'squid_x', 0.0)) + width / 2
        ry = float(getattr(squid, 'squid_y', 0.0)) + height / 2
        # The visitor where it is drawn, or where its body is if not drawn yet.
        node_id = self.visit_node_ids.get(actor.uuid)
        remote = getattr(self.entity_manager, 'remote_squids', None) or {}
        visual = (remote.get(node_id) or {}).get('visual')
        if visual is not None and visual.scene() is not None:
            centre = visual.sceneBoundingRect().center()
            vx, vy = centre.x(), centre.y()
        else:
            vx, vy = actor.x + width / 2, actor.y + height / 2
        return show(actor.uuid, (rx + vx) / 2, (ry + vy) / 2)

    def _resident_swim_frame(self):
        """The frame the resident is drawn with (0 or 1): visitors swim on
        the other one (RemoteEntityManager._swim)."""
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        return getattr(squid, 'current_frame', None)

    def handle_resident_died(self, **kwargs) -> None:
        """This tank's resident has died. End every visit to it.

        Visitors go home with an ordinary visit_end, their encounters are
        written down, and nothing is left pointing at a squid that is about
        to be replaced by its hatchling.
        """
        if self.host_body is not None:
            for actor in list(self.host_body.visitors.values()):
                self.end_visit_as_host(actor, reason=END_EJECTED)
        # It may have died while away visiting: its own visit ends too.
        if self.visitor_mind is not None and self.visitor_mind.perception.away:
            self.visitor_mind.end_visit(reason='departed', notify=True)
        for peer_uuid in list(self.open_encounters):
            self.close_encounter(peer_uuid)
        self.conspecific_view.clear()

    def _resident_is_dead(self) -> bool:
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        lifecycle = getattr(squid, 'lifecycle', None)
        return bool(lifecycle is not None and lifecycle.is_dead)

    #: Two squid this close, with a contest between them, are about to fight.
    FIGHT_CLOUD_RANGE = 250.0

    #: After a fight starts, the same pair cannot start another for this long.
    #: Two squid still face to face are otherwise just in contact - which is
    #: where a mating can happen. The same pause the mobile game uses.
    FIGHT_COOLDOWN = 25.0

    def show_fight_cloud(self, peer_uuid: str) -> bool:
        """A contest has broken out here: draw ONE cloud over the pair.

        Called by ConspecificView.on_contest, on the thread that resolved the
        contest - the visitor's intent being applied, or the resident's own
        actuator - so the drawing happens on Qt's thread. Only when the two
        squid are both in this tank and close; a contest over an object from
        across the tank is not a fight.
        """
        if not peer_uuid or self.entity_manager is None:
            return False
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        presence = self.conspecific_view.presences.get(peer_uuid)
        if squid is None or presence is None:
            return False
        if getattr(squid, 'is_transitioning', False):
            return False            # the resident is away; nobody to fight here
        # A contact or a contest is not a fight. One squid has to start it:
        # the one whose own aggression neuron is the more aggro, if it is
        # more aggro than placid (src/fighting.py). Neither? They are just
        # in contact - playing, competing, perhaps mating.
        start = self._who_starts_a_fight(peer_uuid)
        if start is None:
            return False
        now = self.host_body.clock() if self.host_body is not None else time.time()
        if now < self._fight_cooldown_until.get(peer_uuid, 0.0):
            return False
        rx = float(getattr(squid, 'squid_x', 0.0)) + float(getattr(squid, 'squid_width', 0.0)) / 2
        ry = float(getattr(squid, 'squid_y', 0.0)) + float(getattr(squid, 'squid_height', 0.0)) / 2
        if math.hypot(presence.x - rx, presence.y - ry) > self.FIGHT_CLOUD_RANGE:
            return False
        sequence = getattr(self.entity_manager, 'start_fight_sequence', None)
        actor = self.host_body.visitor(peer_uuid) if self.host_body is not None else None
        if callable(sequence) and actor is not None:
            already_busy = actor.body_busy_until > self.host_body.clock()
            fight_id = str(uuid.uuid4())
            # A fight over an object opens with the object flashing dark red
            # (RemoteEntityManager.CONTEST_LEAD_MS) before the bodies close in.
            contested = getattr(presence, 'contested_item', None)
            lead = getattr(self.entity_manager, 'CONTEST_LEAD_MS', 0) / 1000.0 \
                if contested is not None else 0.0
            started = sequence(peer_uuid, self.visit_node_ids.get(peer_uuid), squid, actor,
                               on_finished=lambda: self.resolve_fight(actor, fight_id),
                               contested=contested)
            if started and not already_busy:
                self._fight_starts[fight_id] = start
                actor.body_busy_until = self.host_body.clock() + lead + 3.2
                self._fight_cooldown_until[peer_uuid] = now + self.FIGHT_COOLDOWN
            return started
        shown = self.entity_manager.show_fight_cloud(
            peer_uuid, (rx + presence.x) / 2, (ry + presence.y) / 2)
        if shown:
            self._fight_cooldown_until[peer_uuid] = now + self.FIGHT_COOLDOWN
        return shown

    def _resident_brain_state(self) -> Dict[str, float]:
        brain = getattr(getattr(self.tamagotchi_logic, 'brain_window', None),
                        'brain_widget', None)
        return dict(getattr(brain, 'state', None) or {})

    def _who_starts_a_fight(self, peer_uuid: str):
        """Which squid starts a fight with the other, and why - or None.

        Read from each squid's own aggression neuron: the resident's here, the
        visitor's from its latest intent (worked out on its own machine).
        """
        actor = self.host_body.visitor(peer_uuid) if self.host_body is not None else None
        mine, why = fighting.fight_predisposition(self._resident_brain_state())
        intent = getattr(actor, 'last_intent', None)
        theirs = float(getattr(intent, 'aggression', 0.0) or 0.0)
        if max(mine, theirs) < fighting.AGGRESSION_THRESHOLD:
            return None
        if mine >= theirs:
            # What the other squid had just done, if it had just taken
            # something: not what decided the fight - its own aggression did
            # that - but what it was aggressive ABOUT, for the record.
            taken = self.conspecific_view.provocation(peer_uuid) \
                if hasattr(self.conspecific_view, 'provocation') else None
            if taken is not None:
                why = dict(why, provoked_by=taken['what'])
            return {'attacker': 'resident', 'why': why}
        return {'attacker': 'visitor', 'why': {'aggression': round(theirs, 1)}}

    def resolve_fight(self, actor, fight_id):
        """Resolve a completed scuffle once, in the host that owns its bodies.

        Not a coin flip: each side's ability - its body, its experience and
        how hard its network commits - decides it (src/fighting.py), with a
        little luck. The whole of it is recorded: who started it and why,
        both sides' abilities, the chance, the consequences.
        """
        if self.host_body is None or self.host_body.visitor(actor.uuid) is not actor:
            return False
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        stats = getattr(squid, 'statistics', None)
        if stats is None or self._resident_is_dead():
            return False
        start = self._fight_starts.pop(fight_id, None) or {'attacker': 'visitor', 'why': {}}
        resident_attacks = start['attacker'] == 'resident'
        fit, fit_why = fighting.squid_fitness(squid)
        mine = fighting.side(self._resident_brain_state(), fit, fit_why,
                             attacking=resident_attacks)
        intent = actor.last_intent
        their_commit = (getattr(intent, 'aggression', 0.0) if not resident_attacks
                        else getattr(intent, 'defence', 0.0))
        their_fit = float(getattr(intent, 'fitness', 1.0) or 0.0) if intent else 1.0
        theirs = {'role': 'defender' if resident_attacks else 'attacker',
                  'fitness': their_fit, 'commitment': round(float(their_commit or 0.0), 1),
                  'committed_by': 'defence' if resident_attacks else 'aggression',
                  'ability': fighting.fighting_ability(their_fit, their_commit or 0.0)}
        record = fighting.resolve_fight(mine, theirs)
        won = record['first_won']
        if not stats.record_fight_result(fight_id, won):
            return False
        record.update(fight_id=fight_id, opponent=actor.identity.name,
                      opponent_uuid=actor.uuid, why=start['why'],
                      consequences=fighting.apply_consequences(squid, won))
        brain = getattr(getattr(self.tamagotchi_logic, 'brain_window', None),
                        'brain_widget', None)
        for thought in fight_thoughts(record, 'first'):
            think(self.tamagotchi_logic, thought)
        if brain is not None:
            record['aggression_rose'] = fighting.scar(
                brain, won, f"{'won' if won else 'lost'} a fight with {actor.identity.name}")
        remember_fight(getattr(squid, 'memory_manager', None), record, me='first')
        session = self.open_encounters.get(actor.uuid)
        if session is not None:
            session.note_fight(won)       # remembered against that individual
        self.announce_fight(won)
        for _ in range(3):
            self.host_body._report(actor, CONSEQUENCE_FIGHT, {
                'fight_id': fight_id, 'won': not won,
                'you_started': not resident_attacks,
                'chance': round(1.0 - record['first_chance'], 3),
                'their_ability': mine['ability'], 'your_ability': theirs['ability']})
        message = f"{squid.name}: {fighting.describe(record, 'first')}"
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(message)
        return True

    def announce_fight(self, won: bool) -> None:
        """This tank's squid has fought, as host or as visitor. Once per fight.

        Lets other plugins (achievements) count it; changes nothing here.
        """
        if self.plugin_manager is None:
            return
        self.plugin_manager.trigger_hook(
            "on_fight", tamagotchi_logic=self.tamagotchi_logic,
            squid=getattr(self.tamagotchi_logic, 'squid', None), won=bool(won))
