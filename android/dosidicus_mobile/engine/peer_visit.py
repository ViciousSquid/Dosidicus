"""Nearby transport adapter for the shared remote-mind encounter protocol.

Only identity, perception, motor intents and physical consequences cross this
link. The visitor's brain, memory and learning stay on its originating device.
Local preview visitors are separate and never used as a network fallback.
"""
import json
import time
from types import SimpleNamespace

from . import shared  # locate src and the Qt-free multiplayer modules
from plugins.multiplayer.encounter import EncounterSession, drive_snapshot
from plugins.multiplayer.host_body import HostBody
from plugins.multiplayer.identity import SquidIdentity, ENCOUNTER_PROTOCOL_VERSION
from plugins.multiplayer.peer_ledger import PeerLedger
from plugins.multiplayer.remote_protocol import (
    ActionIntent, Gamete, ProtocolError, VisitEnd, new_visit_id, LINK_TIMEOUT, MSG_GAMETE,
)
from plugins.multiplayer.visitor_mind import VisitorMind


class Item:
    """A view of a mobile world object, never a copy of its state."""
    def __init__(self, data):
        self.data = data
        self.category = data.get('category', 'food')
        self.filename = data.get('type', '')

    def sceneBoundingRect(self):
        return SimpleNamespace(center=lambda: SimpleNamespace(
            x=lambda: self.data['x'], y=lambda: self.data['y']))

    def __eq__(self, other):
        return isinstance(other, Item) and self.data is other.data


class World:
    def __init__(self, sim, visit):
        self.sim, self.visit = sim, visit
        self.squid = sim.squid
        self.user_interface = SimpleNamespace(scene=self,
            window_width=sim.tank_size[0], window_height=sim.tank_size[1])

    @property
    def food_items(self):
        return [Item(f) for f in self.sim.food_items]

    def items(self):
        carried = self.sim._visitor_carried_rocks()
        return [Item(d) for d in self.sim.decorations
                if d['id'] not in carried and d['id'] not in self.sim._rock_velocities
                and self.sim._rock_cooldowns.get(d['id'], 0.) <= self.squid.brain.sim_time
                and not (self.squid.carrying_rock and d['id'] == self.squid.carried_rock_id)]

    def removeItem(self, item):
        if item.category == 'food':
            if item.data in self.sim.food_items:
                self.sim.food_items.remove(item.data)
        # Held decorations remain in the mobile scene and follow their body.

    def throw_visitor_rock(self, actor, item, intent):
        from src.throwing import out_of_reach, plan_throw
        from src.vision_cone import FACING_ANGLES
        v = self.visit.body
        targets = [(self.squid.name, self.squid.x, self.squid.y)] if self.sim._sees_squid_at(
            actor.x, actor.y, actor.facing, self.squid.x, self.squid.y) else []
        plan = plan_throw({'act_play': intent.activation, 'aggression': intent.aggression},
            (actor.x, actor.y), FACING_ANGLES.get(actor.facing, 0.), targets,
            slowest=6., fastest=20., gravity=.3, drag=.02,
            bounds=(0., float(self.sim.tank_size[0]), 0., float(self.sim.tank_size[1] - 40)),
            practice=getattr(intent, 'practice', 0))
        if out_of_reach(plan):
            # Beyond this throw: the body keeps the rock and closes in.
            return {'closing_in': True, 'target_at': plan['target_at'],
                    'aimed_at': plan['aimed_at']}
        import uuid
        plan.update(throw_id=uuid.uuid4().hex, hit=None, owner=v['id'],
                    source_uuid=actor.uuid, source_name=actor.identity.name,
                    source_identity=actor.identity.to_payload())
        rock = item.data
        rock['x'], rock['y'] = actor.x, min(actor.y, self.sim.tank_size[1] - 40)
        self.sim._rock_throws[rock['id']] = plan
        self.sim._rock_velocities[rock['id']] = [plan['vx'], plan['vy']]
        v['carried_rock'] = None
        return plan

    def ink_visitor(self, actor):
        self.sim.ink_clouds.append({'x': actor.x, 'y': actor.y,
                                   't': self.squid.brain.sim_time, 'ttl': 3.})


class PeerVisit:
    """One consented Nearby link. Transport callbacks execute on the UI thread."""
    def __init__(self, sim, send, hosting=False, clock=time.time):
        self.sim, self.send_bytes, self.hosting, self.clock = sim, send, hosting, clock
        config = sim.lifecycle_config
        self.host = HostBody(World(sim, self), clock=clock,
                             mating_chance=config['mating_chance'],
                             mating_contact_seconds=config['mating_contact_seconds'],
                             on_mating=self._on_mating) if hosting else None
        self.ledger = PeerLedger(sim.squid.memory)
        self.mind = None if hosting else VisitorMind(sim, self.ledger, self.send, clock=clock)
        if self.mind:
            self.mind.on_fight = lambda won: sim.achievements.on_fight()
        self.actor = self.body = self.session = None
        self.closed = False
        self.elapsed = 0.
        self.last_received = clock()
        sim.peer_visits.append(self)

    @property
    def away(self):
        return bool(self.mind and self.mind.perception.away and not self.closed)

    def begin(self):
        """Open the visit. A parent stays with its egg and a dead squid goes
        nowhere, so neither can visit; a dead squid hosts nobody."""
        lifecycle = self.sim.squid.lifecycle
        if (lifecycle.is_dead or not self.hosting and not lifecycle.can_visit
                or self.sim.hatching):
            self.close(notify=False)
            return False
        if self.mind:
            self.mind.begin_visit(None)
        self.send('hello', {'identity': SquidIdentity.from_squid(self.sim.squid).to_payload(),
                            'hosting': self.hosting})
        return True

    def send(self, kind, payload):
        data = json.dumps({'protocol': ENCOUNTER_PROTOCOL_VERSION,
                           'kind': kind, 'payload': payload}, allow_nan=False).encode()
        self.send_bytes(data)
        return True

    def receive(self, data):
        if self.closed or len(data) > 16384:
            return False
        try:
            packet = json.loads(data)
            if packet.get('protocol') != ENCOUNTER_PROTOCOL_VERSION:
                return False
            kind, payload = packet['kind'], packet['payload']
            if kind == 'hello':
                identity = SquidIdentity.from_payload(payload.get('identity', {}))
                if identity is None or bool(payload.get('hosting')) == self.hosting:
                    return False
                if self.host and self.actor is None:
                    visit_id = new_visit_id(self.sim.squid.uuid, identity.uuid)
                    self.actor = self.host.admit(identity, visit_id, 80., self.sim.tank_size[1]/2)
                    self.body = self.sim.add_visitor({'squid': {'uuid': identity.uuid,
                        'personality': identity.personality}}, identity.name, remote=True)
                    self.body.update(x=self.actor.x, y=self.actor.y, uuid=identity.uuid,
                                     report=self.report, peer_visit=self)
                    self.session = EncounterSession(identity, drive_snapshot(self.sim.squid), clock=self.clock)
            elif self.host and self.actor:
                if kind == 'action_intent':
                    intent = ActionIntent.from_payload(payload)
                    if not self.host.apply_intent(self.actor, intent):
                        return False
                elif kind == 'visit_end':
                    end = VisitEnd.from_payload(payload)
                    if end.visit_id != self.actor.visit_id:
                        return False
                    self.close(notify=False)
                elif kind == MSG_GAMETE:
                    if not self._keep_gamete(Gamete.from_payload(payload)):
                        return False
                else:
                    return False
            elif self.mind:
                if kind == 'perception_frame':
                    if not self.mind.on_perception_frame(payload):
                        return False
                elif kind == 'consequence':
                    self.mind.on_consequence(payload)
                elif kind == 'visit_end':
                    end = VisitEnd.from_payload(payload)
                    if end.visit_id != self.mind.visit_id:
                        return False
                    self.close(notify=False)
                else:
                    return False
            self.last_received = self.clock()
            return True
        except (ValueError, TypeError, KeyError, ProtocolError):
            return False

    def _on_mating(self, actor, mating_id):
        """HostBody has resolved a mating with the resident: recorded in its
        lifecycle (which lays the egg and saves), then in the encounter. The
        visitor is told only if this returns True."""
        if actor is not self.actor or not self.sim.record_reproduction(
                mating_id, actor.identity.uuid, actor.identity.name):
            return False
        if self.session is not None:
            self.session.note_mated(mating_id)
        return True

    def _keep_gamete(self, gamete):
        """The mate's half of the egg's weights: kept only for this tank's own
        egg, from that very mating, from the squid that mated - and once. The
        visitor resends it with each announcement of the news; a resend is a
        valid packet that changes nothing."""
        lifecycle = self.sim.squid.lifecycle
        if (gamete.visit_id != self.actor.visit_id or lifecycle.mating_id != gamete.mating_id
                or lifecycle.mate_uuid != self.actor.uuid):
            return False
        self.sim.add_mate_genes(gamete.mating_id, self.actor.identity.name, gamete.genes)
        return True

    def report(self, kind, detail):
        if self.actor is not None and not self.closed:
            self.host._report(self.actor, kind, detail)

    def tick(self, dt):
        if self.closed:
            return
        if self.clock() - self.last_received > LINK_TIMEOUT:
            self.close()
            return
        self.elapsed += dt
        if self.elapsed < .5:
            return
        self.elapsed = 0.
        if self.host and self.actor:
            # The host's housekeeping, as on desktop: news of a mating, repeated
            # over the next round trips, and a visit whose link has gone quiet.
            if self.host.tick():
                self.close()
                return
            actor, v = self.actor, self.body
            if v['fighting']:
                actor.x, actor.y = v['x'], v['y']
            else:
                v.update(x=actor.x, y=actor.y, dir=actor.facing)
            v['carried_rock'] = actor.held_item.data['id'] if actor.held_item else None
            self.sim._carry_rock(v)
            frame = self.host.build_frame(actor)
            self.send('perception_frame', frame.to_payload())
            for consequence in self.host.drain_consequences(actor):
                self.send('consequence', consequence.to_payload())
            if v['leaving']:
                self.close()
        elif self.mind:
            self.mind.tick()

    def close(self, notify=True):
        if self.closed:
            return
        if self.mind:
            self.mind.end_visit(notify=notify)
        if self.host and self.actor:
            for consequence in self.host.drain_consequences(self.actor):
                self.send('consequence', consequence.to_payload())
            if notify:
                self.send('visit_end', VisitEnd(self.actor.visit_id, 'departed').to_payload())
            self.host.remove(self.actor.uuid)
            if self.actor.held_item is not None:
                self.sim.remove_decoration(self.actor.held_item.data['id'])
            if self.body in self.sim.visitors:
                self.sim.visitors.remove(self.body)
            if self.sim.fight and self.sim.fight['visitor_id'] == self.body['id']:
                self.sim._end_fight(None)
            if self.session and self.session.is_memorable():
                record = self.session.close(drives=drive_snapshot(self.sim.squid))
                self.ledger.record(record)
                from src.social_learning import learn_from_encounter
                learn_from_encounter(self.sim.squid.brain, record.valence, record.outcome, record.peer.name)
        self.closed = True
        if self in self.sim.peer_visits:
            self.sim.peer_visits.remove(self)
