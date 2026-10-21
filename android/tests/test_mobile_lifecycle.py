"""Mobile lifecycle parity: the same deaths, headstones, eggs and hatchlings as desktop.

Death is not a game over. A squid dies of neglect, sickness, injuries or - a
parent - starvation (src/lifecycle.py); a headstone bearing its epitaph is laid
where it died, and a new squid hatches in the same tank: from the parent's egg,
with half of each parent's weights, or from a fresh egg. A mating happens only
in a live visit, resolved by the host's HostBody, exactly as on desktop.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from dosidicus_mobile.engine import Simulation                       # noqa: E402
from dosidicus_mobile.engine.peer_visit import PeerVisit               # noqa: E402
from dosidicus_mobile.engine.portability import export_squid, import_squid  # noqa: E402
from src.lifecycle import epitaph                                      # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def run(sim, seconds, step=1.):
    for _ in range(int(seconds / step)):
        sim.update(step)


def headstones(sim):
    return [d for d in sim.decorations if d.get('category') == 'headstone']


def test_neglect_lays_a_headstone_and_a_new_squid_hatches_in_the_same_tank():
    sim = Simulation()
    saves = []
    sim.on_save = lambda: saves.append(sim.squid.lifecycle.stage)
    sim.add_decoration('plant01.png', 'plant', 300., 400.)
    sim.stats.fights_won, sim.stats.fights_lost = 3, 1
    old = sim.squid
    old.name, old.age_seconds = 'Inky', 4000.
    for _ in range(int(sim.lifecycle_config['neglect_seconds']) + 1):
        old.hunger = 100.                     # left at its hungriest
        sim.update(1.)
    assert old.lifecycle.is_dead and old.lifecycle.death_cause == 'neglected'
    assert sim.game_over and old.is_dead and 'dead' in saves
    assert sim.lifecycle_events[-1] == 'Inky has died of neglect.'
    [stone] = headstones(sim)
    assert stone['type'] in Simulation.HEADSTONES
    assert stone['deceased'] == 'Inky' and stone['died_of'] == 'neglected'
    assert epitaph(stone)[0] == 'RIP Inky' and 'Fights won: 3, lost: 1' in epitaph(stone)
    assert stone['age_seconds'] >= 4000.
    generation = sim.generation
    run(sim, Simulation.HATCH_DELAY)
    assert sim.squid is not old and sim.generation == generation + 1
    assert sim.hatching and not sim.game_over
    assert sim.lifecycle_events[-1] == 'Squid is hatching!'
    assert sim.squid.inherited_from == []         # a fresh egg: no parents' weights
    assert sim.stats.fights_won == 0 and sim.squid.statistics is sim.stats
    assert sim.brain_window.brain_widget is sim.squid.brain
    # The tank keeps its decorations and its dead.
    assert headstones(sim) == [stone] and any(d['category'] == 'plant' for d in sim.decorations)
    assert saves[-1] == 'living'


def test_untreated_sickness_kills_and_medicine_starts_the_count_again():
    sim = Simulation()
    sim.squid.is_sick, sim.squid.cleanliness = True, 10.
    run(sim, 300)
    sim.squid.give_medicine()
    sim.squid.cleanliness = 90.
    run(sim, 2)
    assert sim.squid.lifecycle.sick_seconds == 0. and not sim.game_over
    for _ in range(int(sim.lifecycle_config['sickness_seconds']) + 1):
        # Kept sick and fed; grown neurons can otherwise lift cleanliness past
        # 60, which cures it (update_needs).
        sim.squid.is_sick, sim.squid.hunger, sim.squid.cleanliness = True, 0., 30.
        sim.update(1.)
        if sim.game_over:
            break
    assert sim.squid.lifecycle.death_cause == 'sickness'


def test_lethal_injuries_are_a_death_with_a_cause_and_resume_after_load(tmp_path):
    sim = Simulation()
    v = sim.add_visitor(Simulation().to_dict())
    for i in range(50):
        sim._rock_hit(None, dict(throw_id=f'impact-{i}', owner=v['id'], speed=18.))
    sim.update(0.)
    assert sim.squid.lifecycle.death_cause == 'injured' and len(headstones(sim)) == 1
    path = tmp_path / 'dead.zip'
    export_squid(sim, str(path))
    restored = import_squid(str(path))
    assert restored.game_over and restored.squid.lifecycle.death_cause == 'injured'
    run(restored, Simulation.HATCH_DELAY + 1)
    # Resumed exactly once: one new life, one headstone.
    assert restored.generation == 1 and not restored.game_over
    assert len(headstones(restored)) == 1


def test_an_old_save_dead_of_hunger_is_neglect_and_moves_on():
    data = Simulation().to_dict()
    data['squid'].pop('lifecycle')
    data['squid']['is_dead'] = True
    data['game_over'] = True
    sim = Simulation.from_dict(data)
    assert sim.squid.lifecycle.death_cause == 'neglected' and sim.game_over
    run(sim, Simulation.HATCH_DELAY)
    assert sim.generation == 1 and sim.hatching


class Pair:
    """Two devices over a lossless link, the host's mating made certain."""

    def __init__(self):
        self.host, self.guest = Simulation(), Simulation()
        self.host.squid.name, self.guest.squid.name = 'Resident', 'Guest'
        self.host.lifecycle_config['mating_chance'] = 1.
        self.now = 1000.
        self.to_host, self.to_guest = [], []
        self.h = PeerVisit(self.host, self.to_guest.append, hosting=True, clock=lambda: self.now)
        self.g = PeerVisit(self.guest, self.to_host.append, clock=lambda: self.now)
        assert self.h.begin() and self.g.begin()
        self.flush()

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

    def touch(self, seconds=2.5):
        """The two bodies stay in contact for `seconds`: what the host
        resolves after each of the visitor's intents (HostBody._resolve_contact)."""
        actor = self.h.actor
        for _ in range(int(seconds / .5) + 1):
            actor.x, actor.y = self.host.squid.x, self.host.squid.y
            self.h.host._resolve_contact(actor, self.now)
            self.cycle()


def test_a_mating_on_a_mobile_host_lays_an_egg_carrying_both_parents_weights():
    p = Pair()
    p.cycle()
    saves = []
    p.host.on_save = lambda: saves.append(True)
    p.touch()
    lifecycle = p.host.squid.lifecycle
    assert lifecycle.stage == 'parent' and lifecycle.mate_uuid == p.guest.squid.uuid
    assert lifecycle.egg and lifecycle.egg['state'] == 'incubating' and saves
    for _ in range(4):
        p.cycle()                     # the news reaches the guest; its gamete comes back
    assert sorted(lifecycle.egg_genes) == ['Guest', 'Resident']
    assert 'produced an egg' in p.host.lifecycle_events[0]
    # The guest only remembers it: nothing in its own body or lifecycle changes.
    assert p.guest.squid.lifecycle.stage == 'living'
    assert p.g.ledger.has_mated(lifecycle.mating_id) or p.g.mind.session.mating_id
    # A resent - or altered - gamete is not kept twice; one for another
    # mating is refused outright.
    genes = dict(lifecycle.egg_genes['Guest'])

    def gamete(mating_id):
        return json.dumps({'protocol': 4, 'kind': 'gamete', 'payload': {
            'visit_id': p.h.actor.visit_id, 'mating_id': mating_id,
            'genes': {k: 0. for k in genes}}}).encode()
    assert p.h.receive(gamete(lifecycle.mating_id))
    assert not p.h.receive(gamete('another-mating'))
    assert lifecycle.egg_genes['Guest'] == genes


def test_a_parent_does_not_eat_or_visit_and_its_egg_hatches_with_inherited_weights():
    p = Pair()
    p.cycle()
    p.touch()
    for _ in range(4):
        p.cycle()
    sim = p.host
    p.h.close(); p.g.close()
    parent = sim.squid
    # It does not eat: the food stays where it is.
    sim.drop_food(parent.x, parent.y)
    parent.brain.state['act_eat'] = 100.
    assert not sim._try_eat() and sim.food_items
    assert parent.feed() == "won't eat - it has an egg"
    # A parent stays with its egg.
    away = PeerVisit(sim, lambda data: None)
    assert not away.begin() and away.closed
    # It starves, then its egg hatches into a squid with both parents' weights.
    genes = parent.lifecycle.egg_genes
    parent.hunger, parent.health = 100., .05
    sim.update(1.)
    assert parent.lifecycle.death_cause == 'starved'
    run(sim, Simulation.HATCH_DELAY)
    child = sim.squid
    assert child is not parent and child.inherited_from == ['Guest', 'Resident']
    assert sim.lifecycle_events[-1] == 'An egg is hatching!'
    # Every inherited synapse says so, and from whom.
    events = [event for key in sorted(set().union(*genes.values()))
              for event in child.brain.ledger.weight_history(tuple(key.split('->')))
              if event.mechanism == 'inheritance']
    assert events and all(event.detail['parent'] in genes for event in events)
    assert sim.achievements.unlocked.get('circle_of_life')


def test_a_dead_squid_hosts_nobody():
    sim = Simulation()
    sim.squid.lifecycle.die('neglected')
    visit = PeerVisit(sim, lambda data: None, hosting=True)
    assert not visit.begin() and visit not in sim.peer_visits


def test_lifecycle_and_epitaph_round_trip_through_the_desktop_archive(tmp_path):
    sim = Simulation()
    sim.squid.lifecycle.record_reproduction('mating-1', 'mate-uuid', 'Mate', 100., 450.)
    path = tmp_path / 'parent.zip'
    export_squid(sim, str(path))
    import zipfile
    with zipfile.ZipFile(path) as archive:
        game = json.loads(archive.read('game_state.json'))
    assert game['lifecycle']['stage'] == 'parent'
    restored = import_squid(str(path))
    assert restored.squid.lifecycle.mating_id == 'mating-1'
    assert restored.squid.lifecycle.egg['x'] == 100.


def test_the_apk_carries_desktops_headstones():
    shipped = sorted(p.name for p in (ROOT / 'android' / 'assets' / 'headstones').glob('*.png'))
    desktop = sorted(p.name for p in (ROOT / 'images' / 'headstones').glob('*.png'))
    assert shipped == desktop == sorted(Simulation.HEADSTONES)
    for name in shipped:
        assert ((ROOT / 'android' / 'assets' / 'headstones' / name).read_bytes()
                == (ROOT / 'images' / 'headstones' / name).read_bytes())


@pytest.mark.parametrize('stone, lines', [
    ({'deceased': 'Old'}, ['RIP Old']),
    ({'deceased': 'Bob', 'age_seconds': 90061, 'fights_won': 2, 'fights_lost': 5},
     ['RIP Bob', 'Lived 1d 1h', 'Fights won: 2, lost: 5']),
])
def test_epitaph(stone, lines):
    assert epitaph(stone) == lines


def test_a_mobile_resident_recognises_a_visitor_it_remembers_badly():
    from plugins.multiplayer.encounter import EncounterSession, drive_snapshot
    from plugins.multiplayer.identity import SquidIdentity
    from plugins.multiplayer.peer_ledger import PeerLedger
    sim, other = Simulation(), Simulation()
    other.squid.name = 'Bully'
    session = EncounterSession(SquidIdentity.from_squid(other.squid), drive_snapshot(sim.squid))
    session.note_hit(taken=True, what='poop')
    record = session.close(drives=drive_snapshot(sim.squid))
    PeerLedger(sim.squid.memory).record(record)
    seen = {}
    sim.squid.brain.perceive = lambda name, value: seen.__setitem__(name, value)
    v = sim.add_visitor(other.to_dict(), name='Bully')
    v.update(x=sim.squid.x + 100., y=sim.squid.y, leaving=False)
    sim.squid.direction = 'right'
    sim.update(.1)
    assert seen['squid_familiar'] > 0 and seen['squid_recalled_bad'] > 0
    sim.visitors.clear()                            # gone: nobody in view
    sim.update(.1)
    assert seen['squid_familiar'] == 0 and seen['squid_recalled_bad'] == 0
