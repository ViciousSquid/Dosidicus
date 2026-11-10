"""A plant is something the squid SEES, or does not know about.

The brain used to be handed `plant_proximity`: the distance to the nearest
plant, whichever way the squid was facing. That is the game telling the brain
where things are. These tests pin the replacement:

  * the only thing the brain is told is "a plant is in my view cone";
  * no squid is born with a neuron for that - `can_see_plant` is grown the
    first time one is seen, the way `can_see_squid` is for another squid;
  * the squid a player already raised keeps its plant neuron, its synapses and
    its history, under the new name;
  * away in another tank, the host reports a plant by the same view cone.
"""
import json
import math
from pathlib import Path

import pytest

from src.brain_constants import (BINARY_NEURONS, ANALOGUE_SENSORS, GROWN_SENSES,
                                 PLANT_PERCEPT, PLANT_SENSOR, RENAMED_NEURONS,
                                 is_learning_target, newborn_neurons)
from src.brain_io import normalise_brain
from src.portable_brain import HeadlessBrain, TrainingConfig
from src.vision_worker import SceneObject, SquidVisionState, VisionWorker

ROOT = Path(__file__).resolve().parents[1]


def grown(brain):
    return set(brain.positions) - set(newborn_neurons())


# ---------------------------------------------------------------------------
# The sense is grown, on first sight, and never before
# ---------------------------------------------------------------------------
def test_no_squid_is_born_with_a_plant_sense():
    brain = HeadlessBrain()
    assert PLANT_SENSOR not in brain.positions
    assert 'plant_proximity' not in brain.positions
    for _ in range(20):                      # a life with no plant in sight
        brain.perceive(PLANT_PERCEPT, 0.0)
        brain.propagate()
    assert grown(brain) == set()


def test_the_first_plant_it_sees_grows_can_see_plant_and_nothing_else():
    brain = HeadlessBrain()
    growth = brain.enhanced_neurogenesis
    # Even at the brain's size limit and inside a growth cooldown: nothing
    # that already exists could ever stand for it.
    growth.config.neurogenesis['max_neurons'] = len(brain.positions)
    growth.config.neurogenesis['max_per_type'] = {'novelty': 0}
    growth._last_growth_at = 10_000

    brain.perceive(PLANT_PERCEPT, 100.0)
    brain.propagate()

    assert grown(brain) == {PLANT_SENSOR}
    # A sense organ, like can_see_food: on or off, written by the world.
    assert PLANT_SENSOR in BINARY_NEURONS and PLANT_SENSOR not in ANALOGUE_SENSORS
    assert not is_learning_target(PLANT_SENSOR)
    assert not [edge for edge in brain.weights if edge[1] == PLANT_SENSOR]
    assert brain.neuron_shapes[PLANT_SENSOR] == 'square'
    assert brain.state[PLANT_SENSOR] == 100.0
    # ...and it can say why it exists.
    origin = brain.ledger.origins[PLANT_SENSOR]
    assert origin.deficit_summary == 'It saw a plant for the first time'
    assert origin.evidence['concept'] == PLANT_SENSOR
    # It asserts nothing about what a plant is FOR: no path to any action.
    assert not [edge for edge in brain.weights
                if edge[0] == PLANT_SENSOR and edge[1].startswith('act_')]
    # Seen once, it is never grown twice and never pruned.
    brain.propagate()
    assert grown(brain) == {PLANT_SENSOR}
    assert growth.intelligent_pruning() != PLANT_SENSOR


def test_the_sensor_reads_like_can_see_food_on_or_off():
    brain = HeadlessBrain()
    brain.perceive(PLANT_PERCEPT, 100.0)
    brain.propagate()
    assert brain.state[PLANT_SENSOR] == 100.0
    brain.perceive(PLANT_PERCEPT, 0.0)
    brain.propagate()
    assert brain.state[PLANT_SENSOR] == 0.0


def test_a_frozen_brain_perceives_a_plant_and_grows_nothing():
    brain = HeadlessBrain()
    brain.perceive(PLANT_PERCEPT, 100.0)
    brain.propagate(observe_learning=False)
    assert grown(brain) == set()


def test_the_headless_tank_only_reports_a_plant_within_sight():
    from headless.headless_trainer import HeadlessSimulation
    tank = HeadlessSimulation(TrainingConfig(
        seed=5, plants=0, food_spawn_chance=0, poop_spawn_chance=0, startle_chance=0))
    tank.plants = [{'x': 0.95, 'y': 0.95}]            # far corner; squid at centre
    for i in range(10):
        tank.tick = i
        tank._simulation_step()
    assert tank.squid.plant_visible is False
    assert PLANT_SENSOR not in tank.brain.positions

    tank.plants = [{'x': 0.6, 'y': 0.5}]              # within sight
    tank.squid.x, tank.squid.y = 0.5, 0.5
    tank._refresh_food_sense()
    assert tank.squid.plant_visible is True
    tank.tick = 10
    tank._simulation_step()
    assert PLANT_SENSOR in tank.brain.positions


# ---------------------------------------------------------------------------
# The eye: a plant behind the squid is not seen
# ---------------------------------------------------------------------------
def _vision(view_angle, plant_xy):
    worker = VisionWorker.__new__(VisionWorker)       # the calculation only
    squid = SquidVisionState(squid_x=500.0, squid_y=400.0, squid_width=100.0,
                             squid_height=100.0, current_view_angle=view_angle)
    plant = SceneObject(x=plant_xy[0], y=plant_xy[1], width=64.0, height=64.0,
                        category='plant')
    return VisionWorker._calculate_visibility(worker, squid, [plant])


def test_a_plant_in_the_view_cone_is_seen():
    result = _vision(0.0, (800.0, 418.0))             # facing right; plant to the right
    assert result.can_see_plant is True
    assert result.visible_plants


def test_a_plant_right_behind_the_squid_is_not_seen_however_close():
    result = _vision(math.pi, (600.0, 418.0))         # facing left; plant touching, right
    assert result.can_see_plant is False
    assert not hasattr(result, 'plant_proximity_value')
    assert not hasattr(result, 'nearby_plants')


# ---------------------------------------------------------------------------
# A squid someone already raised keeps its plant neuron
# ---------------------------------------------------------------------------
def test_a_saved_brain_carries_its_plant_neuron_over_under_the_new_name():
    assert RENAMED_NEURONS == {'plant_proximity': PLANT_SENSOR}
    old = {
        'neurons': {'hunger': {'position': [0, 0]},
                    'anxiety': {'position': [10, 0]},
                    'plant_proximity': {'position': [50, 250]}},
        'connections': {'plant_proximity->anxiety': -0.3,
                        'hunger->anxiety': 0.2},
        'state': {'hunger': 50, 'anxiety': 40, 'plant_proximity': 37.5},
        'output_bindings': [{'neuron_name': 'plant_proximity',
                             'output_hook': 'neuron_output_seek_plant'}],
    }
    brain = normalise_brain(old)
    assert 'plant_proximity' not in brain['neurons']
    assert PLANT_SENSOR in brain['neurons']
    edges = {(e['source'], e['target']): e['weight'] for e in brain['connections']}
    assert edges[(PLANT_SENSOR, 'anxiety')] == -0.3
    assert edges[('hunger', 'anxiety')] == 0.2
    assert brain['output_bindings'][0]['neuron_name'] == PLANT_SENSOR
    assert 'plant_proximity' not in json.dumps(brain)


def test_the_shipped_plant_seeker_brain_loads_with_a_plant_sense():
    data = json.loads((ROOT / 'custom_brains' / 'Plant-Seeker.json').read_text())
    brain = HeadlessBrain()
    assert brain.load_brain(data)
    assert PLANT_SENSOR in brain.positions
    assert 'plant_proximity' not in brain.positions
    assert (PLANT_SENSOR, 'anxiety') in brain.weights
    # Designed in rather than grown, it is still driven by what is in view.
    brain.perceive(PLANT_PERCEPT, 100.0)
    brain.propagate()
    assert brain.state[PLANT_SENSOR] == 100.0


# ---------------------------------------------------------------------------
# Away in another tank: the host reports a plant by the visitor's view cone,
# and both squid grow can_see_squid the first time they see each other.
# ---------------------------------------------------------------------------
multiplayer = pytest.importorskip('test_remote_mind_stage1')


def _visit(items=(), facing='right'):
    meeting = multiplayer.Encounter(items=items)
    # A real brain on the visitor's side: growth is the point of these tests.
    meeting.visitor_tank.brain_window.brain_widget = HeadlessBrain()
    meeting.admit(x=300.0, y=400.0)
    meeting.actor.facing = facing
    return meeting


def _visitor_brain(meeting):
    return meeting.visitor_tank.brain_window.brain_widget


def test_the_host_reports_a_plant_only_when_the_visitor_is_looking_at_it():
    from plugins.multiplayer.remote_protocol import OBSERVABLE_SENSORS
    assert 'plant_in_view' in OBSERVABLE_SENSORS
    assert 'plant_proximity' not in OBSERVABLE_SENSORS

    plant = multiplayer.FakeItem(500.0, 400.0, category='plant')
    looking = _visit(items=[plant], facing='right')
    assert looking.host_sends_frame().sensors['plant_in_view'] == 100.0

    away = _visit(items=[plant], facing='left')
    assert away.host_sends_frame().sensors['plant_in_view'] == 0.0


def test_a_visitor_grows_its_plant_sense_from_a_plant_in_the_hosts_tank():
    meeting = _visit(items=[multiplayer.FakeItem(500.0, 400.0, category='plant')])
    brain = _visitor_brain(meeting)
    assert PLANT_SENSOR not in brain.positions
    meeting.host_sends_frame()
    meeting.visitor_receives()
    assert brain.percepts['plant_in_view'] == 100.0
    brain.propagate()
    assert PLANT_SENSOR in brain.positions
    assert brain.state[PLANT_SENSOR] == 100.0


def test_a_visiting_squid_grows_can_see_squid_the_first_time_it_sees_the_resident():
    meeting = _visit()                       # the resident is ahead, in view
    brain = _visitor_brain(meeting)
    assert 'can_see_squid' not in brain.positions
    meeting.host_sends_frame()
    meeting.visitor_receives()
    assert brain.percepts['squid_in_view'] == 100.0
    brain.propagate()
    assert 'can_see_squid' in brain.positions
    assert brain.state['can_see_squid'] == 100.0
    origin = brain.ledger.origins['can_see_squid']
    assert origin.evidence['concept'] == 'can_see_squid'
    assert origin.evidence['first_encounter'] is True


def test_a_visitor_facing_away_from_the_resident_grows_nothing():
    meeting = _visit(facing='up')            # the resident is to the right
    brain = _visitor_brain(meeting)
    meeting.host_sends_frame()
    meeting.visitor_receives()
    brain.propagate()
    assert 'can_see_squid' not in brain.positions


def test_the_resident_grows_can_see_squid_when_a_visitor_swims_into_its_view():
    """At home the vision worker reports the visitor as a squid in the cone,
    and that percept is all it takes (TamagotchiLogic.apply_input_neurons_to_brain
    calls perceive('squid_in_view') from the worker's result)."""
    worker = VisionWorker.__new__(VisionWorker)
    resident = SquidVisionState(squid_x=500.0, squid_y=400.0, squid_width=100.0,
                                squid_height=100.0, current_view_angle=0.0)
    visitor = SceneObject(x=800.0, y=418.0, category='squid')
    seen = VisionWorker._calculate_visibility(worker, resident, [visitor])
    assert seen.can_see_squid is True

    brain = HeadlessBrain()
    brain.perceive('squid_in_view', 100.0 if seen.can_see_squid else 0.0)
    brain.propagate()
    assert 'can_see_squid' in brain.positions
    assert set(GROWN_SENSES) >= {'can_see_squid', PLANT_SENSOR}


# ---------------------------------------------------------------------------
# A grown neuron grows into place, as the hatching ones do
# ---------------------------------------------------------------------------
def test_a_grown_sense_swells_into_place_like_a_hatching_neuron():
    import time
    from PyQt5 import QtWidgets
    from src.brain_constants import NEURON_REVEAL_DURATION, reveal_scale
    from src.brain_widget import BrainWidget
    from src.config_manager import ConfigManager

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    brain = BrainWidget(config=ConfigManager())
    for name in ('neurogenesis_timer', 'animation_timer', '_render_timer',
                 '_brain_export_timer', '_link_fade_timer'):
        timer = getattr(brain, name, None)
        if timer is not None:
            timer.stop()
    brain._cleanup_render_worker()
    try:
        assert PLANT_SENSOR not in brain.neuron_reveal_animations
        brain.perceive(PLANT_PERCEPT, 100.0)
        brain.propagate_activations()

        assert PLANT_SENSOR in brain.neuron_positions
        assert PLANT_SENSOR in brain.visible_neurons
        growing = brain.neuron_reveal_animations[PLANT_SENSOR]
        assert abs(growing['start_time'] - time.time()) < 2.0
        # It starts from nothing and is drawn at the hatch animation's size.
        assert reveal_scale(0.0) < 0.2
        assert reveal_scale(NEURON_REVEAL_DURATION) == 1.0

        # ...and the animation finishes and clears itself like any reveal.
        growing['start_time'] -= NEURON_REVEAL_DURATION + 0.1
        brain.update_animations()
        assert PLANT_SENSOR not in brain.neuron_reveal_animations
        assert PLANT_SENSOR in brain.visible_neurons
    finally:
        brain.deleteLater()
