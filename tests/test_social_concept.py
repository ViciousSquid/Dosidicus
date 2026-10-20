"""Other squid are sensed, and the brain grows what it needs for them - from experience.

The rules these hold the engine to:
  * nothing is innate for other squid, and nothing is chosen for the squid:
    a sense organ grows the first time its concept matters (can_see_squid on
    the first sighting, squid_nearby, recognises_squid, remembers_*), and a
    social neuron the first time the squid's own network does the thing with
    another squid in view (social_play, social_flee) or is in a fight
    (social_fight);
  * the senses are written by the world like can_see_food, never by a
    synapse; can_see_squid and recognises_squid are tick boxes;
  * social neurons are hexagons named for their purpose - one of each - fed
    by the senses and driving the squid's existing actions;
  * personality enters only as the first sense organ's wiring;
  * every one carries its cause, and the Laboratory says what it represents;
  * a squid that never meets another grows none of them;
  * a brain saved with the old conspecific_* neurons loads without them.
"""
import math
import sys
from pathlib import Path

import pytest

from src.brain_constants import (ACTION_THRESHOLDS, BINARY_NEURONS, RETIRED_NEURONS,
                                 SOCIAL_NEURONS, SOCIAL_SENSORS, SQUID_SENSORS,
                                 is_learning_target,
                                 newborn_neurons)
from src.decision_engine import wants
from src.portable_brain import HeadlessBrain


def live(brain, ticks=1, **percepts):
    """`ticks` of life with these percepts, the drives moved as the game moves them."""
    percepts.setdefault('squid_in_view', 100.)
    for _ in range(ticks):
        for name, value in percepts.items():
            brain.perceive(name, value)
        for stat, delta in brain.compute_neural_modulation().items():
            brain.state[stat] = max(0., min(100., brain.state[stat] + delta))
        brain.propagate()
    return brain


def newborn(personality='adventurous'):
    brain = HeadlessBrain()
    brain.personality = personality
    return brain


def grown(brain):
    return set(brain.positions) - set(newborn_neurons())


@pytest.mark.parametrize('personality', ['adventurous', 'timid'])
def test_first_sighting_grows_the_can_see_squid_sense_organ_and_nothing_else(personality):
    brain = newborn(personality)
    growth = brain.enhanced_neurogenesis
    assert growth.observe_social() is None          # nothing in view
    # The first sighting grows it even at a configured growth cap/cooldown.
    growth.config.neurogenesis['max_neurons'] = len(brain.positions)
    growth.config.neurogenesis['max_per_type'] = {'novelty': 0}
    growth._last_growth_at = 10_000
    brain.perceive('squid_in_view', 100.)
    assert growth.observe_social() == 'can_see_squid'
    assert grown(brain) == {'can_see_squid'}
    assert not RETIRED_NEURONS & set(brain.positions)
    # A sense organ, like can_see_food: a tick box, written by the world.
    assert 'can_see_squid' in BINARY_NEURONS
    assert not is_learning_target('can_see_squid')
    assert not [edge for edge in brain.weights if edge[1] == 'can_see_squid']
    assert brain.neuron_shapes['can_see_squid'] == 'square'
    origin = brain.ledger.origins['can_see_squid']
    assert origin.deficit_summary == 'Other squid encountered!'
    assert origin.evidence['concept'] == 'can_see_squid'
    assert origin.wiring
    # Personality is its wiring, nothing else.
    if personality == 'timid':
        assert brain.weights['can_see_squid', 'act_flee'] > 0
        assert brain.weights['can_see_squid', 'anxiety'] > 0
        assert ('can_see_squid', 'act_play') not in brain.weights
    else:
        assert brain.weights['can_see_squid', 'act_play'] > 0
        assert brain.weights['can_see_squid', 'curiosity'] > 0
        assert ('can_see_squid', 'act_flee') not in brain.weights
    assert growth.intelligent_pruning() != 'can_see_squid'


def test_the_sensor_reads_like_can_see_food_on_or_off():
    brain = live(newborn())
    assert brain.state['can_see_squid'] == 100.
    live(brain, squid_in_view=0.)
    assert brain.state['can_see_squid'] == 0.
    live(brain, squid_in_view=100.)
    assert brain.state['can_see_squid'] == 100.


def test_a_bold_squid_goes_at_another_and_grows_social_play_from_doing_it():
    brain = live(newborn('adventurous'), ticks=6)
    assert wants('act_play', brain.state['act_play'])
    assert 'social_play' in grown(brain)
    assert brain.neuron_shapes['social_play'] == 'hexagon'
    assert not brain.is_connector_neuron('social_play')
    assert brain.weights['can_see_squid', 'social_play'] > 0
    assert brain.weights['social_play', 'act_play'] > 0
    origin = brain.ledger.origins['social_play']
    assert origin.deficit_summary == 'It played with another squid and had no neuron for that'
    assert origin.evidence['experienced'] == 'act_play'
    # Out of view, the senses fall silent and the urge goes with them.
    live(brain, ticks=10, squid_in_view=0.)
    assert brain.state['can_see_squid'] == 0.
    assert brain.state['act_play'] < ACTION_THRESHOLDS['act_play']


def test_a_timid_squid_flees_and_grows_social_flee_from_doing_it():
    brain = newborn('timid')
    fled = False
    for _ in range(20):
        live(brain)
        fled = fled or wants('act_flee', brain.state['act_flee'])
    assert fled
    assert 'social_flee' in grown(brain) and 'social_play' not in grown(brain)
    # Wired to the moment it grew: it drives the flight it was doing, and
    # nothing says it must hold back play - that would be a rule.
    assert brain.weights['social_flee', 'act_flee'] > 0
    assert ('social_flee', 'act_play') not in brain.weights
    assert not wants('act_play', brain.state['act_play'])


def test_a_squid_that_does_nothing_about_another_grows_no_social_neuron():
    """Nothing is chosen for it: an introvert that only watches has nothing to represent."""
    brain = live(newborn('introvert'), ticks=8)
    assert grown(brain) == {'can_see_squid'}


def test_being_in_a_fight_grows_social_fight():
    brain = live(newborn(), ticks=1)
    live(brain, in_fight=100.)
    assert 'social_fight' in grown(brain)
    origin = brain.ledger.origins['social_fight']
    assert origin.evidence['experienced'] == 'in_fight'
    assert brain.weights['can_see_squid', 'social_fight'] > 0
    assert brain.neuron_shapes['social_fight'] == 'hexagon'
    # Fed by what it sensed and felt; driving only what it was doing then.
    from src.brain_constants import ACTION_NEURONS, CORE_STAT_NEURONS
    for src, dst, weight, _purpose in origin.wiring:
        if dst == 'social_fight':
            assert src in SOCIAL_SENSORS or src in CORE_STAT_NEURONS
        else:
            assert src == 'social_fight' and dst in ACTION_NEURONS and weight > 0


def test_each_sense_grows_the_first_time_its_concept_matters_and_feeds_the_social_neurons():
    brain = live(newborn(), ticks=1)
    live(brain, in_fight=100.)                       # social_fight first
    live(brain, ticks=2, squid_proximity=30.)
    assert 'squid_nearby' not in grown(brain)        # not close enough to matter
    live(brain, ticks=1, squid_proximity=70.)
    assert 'squid_nearby' in grown(brain)
    assert brain.weights['squid_nearby', 'social_fight'] > 0
    assert brain.state['squid_nearby'] == 70.       # analogue, as the world reports it
    live(brain, ticks=1, squid_familiar=40.)
    assert 'recognises_squid' in grown(brain) and 'recognises_squid' in BINARY_NEURONS
    live(brain, ticks=1, squid_familiar=40., squid_recalled_bad=55.)
    assert 'remembers_bad_encounter' in grown(brain)
    # It feeds the social neuron that was active when it grew.
    assert brain.weights['remembers_bad_encounter', 'social_fight'] > 0
    live(brain, ticks=1, squid_familiar=40., squid_recalled_good=30.)
    assert 'remembers_good_encounter' in grown(brain)
    for sense in SQUID_SENSORS:
        assert not [edge for edge in brain.weights if edge[1] == sense]
        assert brain.ledger.origins[sense].deficit_summary


def test_one_of_each_never_a_second():
    brain = live(newborn('energetic'), ticks=30, in_fight=100.)
    names = grown(brain)
    assert not [n for n in names if n[-1].isdigit()]
    assert {n for n in names if n.startswith('social')} <= set(SOCIAL_NEURONS)


def test_only_can_see_squid_ignores_the_global_cap():
    brain = newborn()
    brain.enhanced_neurogenesis.config.neurogenesis['max_neurons'] = len(brain.positions)
    live(brain, ticks=8)
    assert grown(brain) == {'can_see_squid'}


def test_lifetime_without_peers_never_grows_any():
    brain = newborn()
    live(brain, ticks=120, squid_in_view=0., squid_proximity=90., in_fight=100.)
    assert set(brain.positions) == set(newborn_neurons())
    assert not any(fn.represents_concept for fn in brain.enhanced_neurogenesis.functional_neurons.values())


def test_the_laboratory_says_what_each_was_created_to_represent():
    from PyQt5 import QtWidgets
    from src.laboratory import NeuronLaboratory
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    brain = live(newborn(), ticks=6)
    lab = NeuronLaboratory.__new__(NeuronLaboratory)
    lab.bw = brain
    cards = []

    def text(name):
        cards.append(lab._card_identity(name))      # keep the card alive to read it
        return cards[-1].findChild(QtWidgets.QLabel).text()

    assert ('This neuron was created to represent the binary concept of '
            '"I see another squid".') in text('can_see_squid')
    assert 'A sense organ the squid grew for itself' in text('can_see_squid')
    assert 'the concept of "playing with another squid"' in text('social_play')
    del app


def test_concept_and_cause_survive_a_fresh_trainer_import():
    brain = live(newborn(), ticks=6)
    loaded = HeadlessBrain()
    assert loaded.load_brain(brain.export_brain())
    growth = loaded.enhanced_neurogenesis
    assert growth.functional_neurons['can_see_squid'].represents_concept == 'can_see_squid'
    assert loaded.ledger.origins['can_see_squid'].deficit_summary == 'Other squid encountered!'
    assert loaded.neuron_shapes['social_play'] == 'hexagon'
    # Still the world's to write, after the reload, and still binary.
    loaded.perceive('squid_in_view', 0.)
    loaded.propagate()
    assert loaded.state['can_see_squid'] == 0.
    assert growth.observe_social() is None


def test_a_save_with_the_old_sensor_neurons_loads_without_them():
    brain = live(newborn(), ticks=6)
    data = brain.export_brain()
    neurons = data['neurons']
    neurons['conspecific_visible'] = dict(position=[350, 50], activation=0, is_custom=False)
    neurons['conspecific_recalled_bad'] = dict(position=[450, 350], activation=0, is_custom=False)
    data['connections'] += [dict(source='conspecific_visible', target='social_play', weight=.9),
                            dict(source='conspecific_recalled_bad', target='anxiety', weight=.4)]
    loaded = HeadlessBrain()
    assert loaded.load_brain(data)
    assert not RETIRED_NEURONS & set(loaded.positions)
    assert not [edge for edge in loaded.weights if RETIRED_NEURONS & set(edge)]
    assert loaded.weights['social_play', 'act_play'] > 0


def test_vision_sees_another_squid_only_in_its_view_cone():
    import math
    from src.vision_worker import (VisionWorker, SquidVisionState, SceneObject,
                                   in_view_cone)
    worker = VisionWorker.__new__(VisionWorker)
    squid = SquidVisionState(squid_x=400, squid_y=300, squid_width=60, squid_height=40,
                             current_view_angle=0.0, window_width=1280,
                             window_height=900)
    ahead = SceneObject(x=700, y=300, width=60, height=40, category='squid')
    behind = SceneObject(x=100, y=300, width=60, height=40, category='squid')
    assert worker._calculate_visibility(squid, [ahead]).can_see_squid
    assert not worker._calculate_visibility(squid, [behind]).can_see_squid
    assert in_view_cone(0, 0, math.pi, math.pi / 2.5, 500, -100, 0)
    assert not in_view_cone(0, 0, 0.0, math.pi / 2.5, 500, -100, 0)


def test_a_drawn_squid_is_a_scene_object_vision_sees_and_a_hidden_one_is_not():
    from PyQt5 import QtWidgets
    from src.vision_worker import extract_scene_objects
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    scene = QtWidgets.QGraphicsScene()
    shown, hidden = scene.addRect(0, 0, 60, 40), scene.addRect(0, 0, 60, 40)
    shown.category = hidden.category = 'squid'
    hidden.setVisible(False)
    squids = [o for o in extract_scene_objects(scene, [], []) if o.category == 'squid']
    assert len(squids) == 1
    del app


def test_mobile_grows_the_sense_for_a_squid_it_can_see_and_keeps_it(tmp_path):
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    sim = Simulation()
    sim._fight_cooldown = 100.
    visitor = sim.add_visitor(Simulation().to_dict(), name='Visitor')
    visitor['x'], visitor['y'] = -300., 200.
    sim.update(1.)
    assert not any(n.represents_concept for n in sim.squid.brain.enhanced_neurogenesis.functional_neurons.values())
    # In the tank, facing the resident from far enough off that the step the
    # resident takes first cannot carry it out of the visitor's cone; the
    # resident turns to the visitor as it comes in.
    right_side = sim.squid.x < sim.tank_size[0] / 2
    visitor['x'] = sim.squid.x + (350. if right_side else -350.)
    visitor['y'], visitor['dir'] = sim.squid.y, 'left' if right_side else 'right'
    sim.update(1.)
    assert 'can_see_squid' in sim.squid.brain.positions
    assert sim.newborn_neuron == 'can_see_squid'
    assert not RETIRED_NEURONS & set(sim.squid.brain.positions)
    assert 'can_see_squid' in sim._visitor_minds[visitor['id']].brain.positions
    path = tmp_path / 'pet.zip'
    sim.save(path)
    restored = Simulation.load(path)
    assert restored.squid.brain.ledger.origins['can_see_squid'].deficit_summary == 'Other squid encountered!'
    restored.visitors.clear()
    restored.update(1.)
    assert restored.squid.brain.state['can_see_squid'] == 0.


def _desktop_squid(x=400., y=300., angle=0.):
    from src.squid import Squid
    squid = Squid.__new__(Squid)
    squid.squid_x, squid.squid_y, squid.squid_width, squid.squid_height = x, y, 60, 40
    squid.current_view_angle, squid.view_cone_angle = angle, math.pi / 2.5
    squid.is_sleeping, squid.view_cone_visible, squid.view_cone_item = False, False, None
    return squid


def _sees(squid):
    from src.vision_worker import VisionWorker, SquidVisionState, extract_scene_objects
    state = SquidVisionState(squid_x=squid.squid_x, squid_y=squid.squid_y,
                             squid_width=60, squid_height=40,
                             current_view_angle=squid.current_view_angle,
                             view_cone_angle=squid.view_cone_angle,
                             window_width=1280, window_height=900)
    return VisionWorker.__new__(VisionWorker)._calculate_visibility(
        state, extract_scene_objects(squid._scene, [], [])).can_see_squid


def test_a_squid_appearing_swings_the_view_cone_onto_it_and_vision_sees_it():
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    squid = _desktop_squid(angle=0.)                 # looking right
    squid._scene = QtWidgets.QGraphicsScene()
    visitor = squid._scene.addRect(0, 0, 60, 40)
    visitor.category = 'squid'
    visitor.setPos(50., 300.)                        # comes in behind it
    assert not _sees(squid)
    assert squid.notice(visitor)
    assert _sees(squid)
    # Scanning does not look away while the gaze holds; the cone follows it.
    visitor.setPos(400., 700.)
    squid.change_view_cone_direction()
    assert _sees(squid)
    # Then the hold is over and scanning takes over again.
    squid._noticed_until = 0.
    assert not squid._look_at_noticed()
    # Gone from the tank: nothing holds the gaze.
    assert squid.notice(visitor)
    squid._scene.removeItem(visitor)
    assert not squid._look_at_noticed()
    del app


def test_asleep_a_squid_notices_nothing():
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    squid = _desktop_squid(angle=0.)
    squid.is_sleeping = True
    scene = QtWidgets.QGraphicsScene()
    visitor = scene.addRect(0, 0, 60, 40)
    visitor.setPos(50., 300.)
    assert not squid.notice(visitor)
    assert squid.current_view_angle == 0.
    del app


def test_mobile_resident_turns_to_a_visitor_coming_into_the_tank():
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    sim = Simulation()
    sim._fight_cooldown = 100.
    squid = sim.squid
    squid.direction = 'right'
    visitor = sim.add_visitor(Simulation().to_dict(), name='Visitor')
    visitor['x'], visitor['y'] = -40., squid.y           # outside: not yet arrived
    sim.update(.1)
    assert not squid.noticing
    visitor['x'] = squid.x - 150.                          # in the tank, behind it
    visitor['vx'] = 0.
    sim.update(.1)
    assert squid.noticing
    assert squid.direction == 'left'
    assert squid.brain.percepts['squid_in_view'] == 100.
    # It watches it while the gaze holds, whichever way it swims...
    squid._step(1., 0.)
    assert squid.direction == 'left'
    # ...and once the hold is over, swimming turns it again.
    squid.brain.sim_time += Simulation().squid.NOTICE_SECONDS + 1.
    squid._step(1., 0.)
    assert squid.direction == 'right'
    # An arrival is noticed once, not every tick it is in the tank.
    sim.update(.1)
    assert not squid.noticing


@pytest.mark.parametrize('anxiety, wired', [(85., True), (50., False)])
def test_what_a_new_sense_means_is_the_moment_it_grew_not_a_rule(anxiety, wired):
    """A bad memory sensed while anxious is wired to anxiety; sensed calmly, it
    is not. Nothing says what a bad memory means - only what was felt."""
    brain = live(newborn(), ticks=1)
    brain.state['anxiety'] = anxiety
    live(brain, ticks=1, squid_familiar=40., squid_recalled_bad=55.)
    live(brain, ticks=1, squid_familiar=40., squid_recalled_bad=55.)
    assert 'remembers_bad_encounter' in grown(brain)
    assert (('remembers_bad_encounter', 'anxiety') in brain.weights) is wired
