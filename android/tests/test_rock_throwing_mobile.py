"""Mobile rock parity, APK portability and a two-device remote brain round trip."""
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from dosidicus_mobile.engine import Simulation
from dosidicus_mobile.engine.peer_visit import PeerVisit
from dosidicus_mobile.engine.portability import export_squid, import_squid
from src.brain_constants import ACTION_NEURONS
from src.throwing import plan_throw
from plugins.multiplayer.remote_protocol import Consequence, CONSEQUENCE_HIT


def quiet(sim, **actions):
    for n in ACTION_NEURONS:
        sim.squid.brain.state[n] = 0.
    sim.squid.brain.state.update(actions)


def carried(sim):
    sim.add_decoration('rock01.png', 'rock', sim.squid.x, sim.squid.y)
    rock = sim.decorations[-1]
    sim.squid.carrying_rock = True
    sim.squid.carried_rock_id = rock['id']
    sim.squid._carry_until = 0.
    return rock


def test_mobile_throw_is_shared_plan_and_drops_when_play_loses():
    sim = Simulation(); rock = carried(sim)
    quiet(sim, act_play=90.)
    sim._update_rock_play(0.)
    expected = plan_throw(sim.squid.brain.state, (sim.squid.x, sim.squid.y), 0., [],
                          slowest=6, fastest=20, gravity=.3)
    plan = sim._rock_throws[rock['id']]
    assert (plan['vx'], plan['vy']) == (expected['vx'], expected['vy'])
    assert plan['driven_by'] == 'act_play' and plan['drive'] == 90.
    assert not sim.squid.carrying_rock
    other = Simulation(); dropped = carried(other)
    quiet(other, act_play=60., act_flee=100.)
    other._update_rock_play(0.)
    assert not other._rock_velocities and not other.squid.carrying_rock
    assert dropped in other.decorations


@pytest.mark.parametrize('dt', [.05, .5, 1.])
def test_mobile_fast_floor_hit_startles_and_records_once(dt):
    sim = Simulation()
    v = sim.add_visitor(Simulation().to_dict(), name='Guest')
    v.update(x=170., y=445., leaving=False)
    sim.squid.x, sim.squid.y = 100., 420.
    rock = carried(sim)
    plan = sim._throw_rock(rock, sim.squid)
    # Exercise a path whose endpoint would skip the body, including landing.
    plan['vx'], plan['vy'] = 200., 60.
    sim._rock_velocities[rock['id']] = [200., 60.]
    sim._fly_rocks(dt)
    mind = sim._visitor_minds[v['id']]
    assert mind.health == 98. and mind.is_startled
    sim._rock_hit(v['id'], plan)
    assert mind.health == 98.
    memories = mind.memory.short_term + mind.memory.long_term
    assert len([m for m in memories if m['category'] == 'social']) == 1


def test_mobile_health_and_rock_memory_survive_archive(tmp_path):
    sim = Simulation()
    v = sim.add_visitor(Simulation().to_dict(), name='Guest')
    plan = dict(throw_id='impact', owner=v['id'], speed=18.)
    sim._rock_hit(None, plan)
    assert sim.squid.health == 98.
    output = tmp_path / 'squid.zip'
    export_squid(sim, str(output))
    restored = import_squid(str(output))
    assert restored.squid.health == 98.
    memories = restored.squid.memory.short_term + restored.squid.memory.long_term
    assert any(m['key'] == 'rock:impact' for m in memories)


class Pair:
    def __init__(self):
        self.host, self.guest = Simulation(), Simulation()
        self.now = 1000.
        self.to_host, self.to_guest = [], []
        self.h = PeerVisit(self.host, self.to_guest.append, hosting=True, clock=lambda: self.now)
        self.g = PeerVisit(self.guest, self.to_host.append, clock=lambda: self.now)
        self.h.begin(); self.g.begin(); self.flush()

    def flush(self):
        while self.to_host or self.to_guest:
            while self.to_host:
                assert self.h.receive(self.to_host.pop(0))
            while self.to_guest:
                assert self.g.receive(self.to_guest.pop(0))

    def cycle(self):
        self.now += .5
        self.h.tick(.5); self.flush()
        self.g.tick(.5); self.flush()


def test_live_mobile_two_device_hit_stays_on_home_brain_and_is_idempotent():
    p = Pair()
    assert p.host._visitor_minds == {}  # no second brain on the host
    assert p.guest.squid.is_transitioning
    original_brain = p.guest.squid.brain
    p.cycle()  # acquire host perception and open the encounter
    packet = Consequence(p.h.actor.visit_id, CONSEQUENCE_HIT, detail={
        'throw_id': 'one-hit', 'speed': 19., 'peer_uuid': p.host.squid.uuid}).to_payload()
    wire = json.dumps({'protocol': 4, 'kind': 'consequence', 'payload': packet}).encode()
    assert p.g.receive(wire) and p.g.receive(wire)
    assert p.guest.squid.health == 98. and p.guest.squid.is_startled
    assert p.host.squid.health == 100.
    assert p.guest.squid.brain is original_brain
    assert p.g.mind.session.hits_taken == 1
    signals = p.guest.squid.sync_stats_to_brain(False)
    assert signals['is_startled'] == 100. and signals['threat_level'] == 100.
    p.guest.squid.brain.advance(1., signals)
    assert p.guest.squid.brain.state['is_startled'] == 100.
    p.g.close(); p.flush()
    memories = p.guest.squid.memory.short_term + p.guest.squid.memory.long_term
    assert any(m['category'] == 'social' and m['value'].get('detail', {}).get('hits_taken') == 1
               for m in memories if isinstance(m.get('value'), dict))


def test_live_mobile_guest_can_throw_back_from_its_own_neural_intent():
    p = Pair()
    p.host.squid.x, p.host.squid.y = 240., 250.
    p.h.actor.x, p.h.actor.y, p.h.actor.facing = 80., 250., 'right'
    p.host.add_decoration('rock01.png', 'rock', 85., 250.)
    quiet(p.guest, act_play=95.)
    p.cycle()  # picks up the nearer rock
    assert p.h.actor.held_item is not None
    p.cycle()  # next play intent throws what it holds
    assert p.h.actor.held_item is None
    plan = next(iter(p.host._rock_throws.values()))
    assert plan['driven_by'] == 'act_play' and plan['drive'] == 95.
    assert plan['aimed_at'] == p.host.squid.name
    for _ in range(30):
        p.host._fly_rocks(.05)
    p.cycle()
    assert p.host.squid.health == 98. and p.host.squid.is_startled
    assert p.guest.squid.health == 100.
    assert p.g.mind.session.hits_given == 1
    assert p.h.session.hits_taken == 1
    assert p.host._visitor_minds == {}
    p.g.close(); p.flush()


def test_live_mobile_link_loss_restores_body_and_keeps_consequences():
    p = Pair(); p.cycle()
    p.guest.squid.health = 98.
    p.now += 100.
    p.g.tick(.5)
    assert p.g.closed and not p.guest.squid.is_transitioning
    assert p.guest.squid.can_move and p.guest.squid.health == 98.
