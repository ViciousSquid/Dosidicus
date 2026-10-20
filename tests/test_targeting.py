"""Which squid a squid goes at: the nearest - and especially one it remembers badly.

Of the squid in view, a throw (rock or poop) and the swim at a squid when at
play go at one this squid remembers badly before any it does not - the worst
remembered first, the nearest among equals; with none remembered badly,
simply the nearest. The memory is the squid's own (PeerLedger), never anything
the other squid or its host says. Why it chose that one is in the plan.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import throwing                                             # noqa: E402
from test_rock_throwing import tank                                  # noqa: E402,F401  (fixture)
from test_remote_mind_stage1 import quiet_brain                      # noqa: E402


def test_with_nobody_remembered_badly_it_is_the_nearest():
    name, *_, why = throwing.choose_target((0., 0.), [('Far', 500., 0.), ('Near', 200., 0.)])
    assert name == 'Near' and why == {'chosen_because': 'nearest'}


def test_one_remembered_badly_is_gone_at_before_a_nearer_stranger():
    name, x, y, why = throwing.choose_target(
        (0., 0.), [('Stranger', 150., 0., 0.), ('Bully', 600., 0., 40.), ('Pest', 700., 0., 10.)])
    assert (name, x) == ('Bully', 600.)
    assert why == {'chosen_because': 'remembered badly', 'recalled_bad': 40.}
    # Equally bad: the nearer.
    assert throwing.choose_target((0., 0.), [('A', 600., 0., 40.), ('B', 300., 0., 40.)])[0] == 'B'


def test_a_desktop_throw_goes_at_the_squid_it_remembers_badly(tank, monkeypatch):
    stranger = tank.item(300, 200, 'squid', 'Stranger')
    bully = tank.item(450, 200, 'squid', 'Bully')
    stranger.peer_uuid, bully.peer_uuid = 'stranger-uuid', 'bully-uuid'
    monkeypatch.setattr(throwing, 'recalled_bad',
                        lambda memory, uuid: 55. if uuid == 'bully-uuid' else 0.)
    tank.state.clear(); tank.state.update(quiet_brain(act_play=50., aggression=100.))
    assert tank.manager.throw_rock()
    plan = tank.manager.current_throw
    assert plan['aimed_at'] == 'Bully' and plan['chosen_because'] == 'remembered badly'
    assert 'whom it remembers badly' in throwing.describe(plan)


def test_a_mobile_squid_throws_at_and_plays_at_the_squid_it_remembers_badly():
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    from plugins.multiplayer.encounter import EncounterSession, drive_snapshot
    from plugins.multiplayer.identity import SquidIdentity
    from plugins.multiplayer.peer_ledger import PeerLedger
    sim = Simulation()
    sim._fight_cooldown = 1e9
    squid = sim.squid
    squid.x, squid.y, squid.direction = 100., 300., 'right'
    bully_sim = Simulation()
    bully_sim.squid.name = 'Bully'
    session = EncounterSession(SquidIdentity.from_squid(bully_sim.squid), drive_snapshot(squid))
    session.note_hit(taken=True, what='poop')
    PeerLedger(squid.memory).record(session.close(drives=drive_snapshot(squid)))
    near = sim.add_visitor(Simulation().to_dict(), name='Stranger')
    far = sim.add_visitor(bully_sim.to_dict(), name='Bully')
    near.update(x=250., y=300., leaving=False)
    far.update(x=380., y=300., leaving=False)
    assert sim._grudge(far) > 0 and sim._grudge(near) == 0
    assert sim._squid_to_play_at(squid.x, squid.y, 'right',
                                 [(v['x'], v['y'], sim._grudge(v)) for v in (near, far)]) == (380., 300.)
    sim.decorations.append({'id': 'r1', 'category': 'rock', 'x': squid.x, 'y': squid.y - 26})
    squid.carrying_rock, squid.carried_rock_id, squid._carry_until = True, 'r1', 0.
    squid.brain.state.update(quiet_brain(act_play=50., aggression=100.))
    sim.stats.rocks_thrown = 500
    sim._update_rock_play(1 / 30)
    plan = sim._rock_throws['r1']
    assert plan['aimed_at'] == 'Bully' and plan['chosen_because'] == 'remembered badly'
