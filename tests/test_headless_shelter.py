"""Spatial shelter affordance: only a selected action near a real plant gives relief.

This is an experimental headless world opt-in. The default trainer's original
stochastic plant proximity is unchanged when set_plants() is not called.
"""
import math

from headless.headless_trainer import HeadlessSimulation
from src.portable_brain import TrainingConfig


def aquarium():
    return HeadlessSimulation(TrainingConfig(
        seed=7, learning_enabled=False, neurogenesis_enabled=False,
        food_spawn_chance=0, startle_chance=0, poop_spawn_chance=0))


def test_spatial_plant_approach_is_consequence_of_selected_shelter():
    sim = aquarium()
    sim.set_plants([{"x": .70, "y": .50}])
    sim.squid.anxiety = 90
    before = (sim.squid.x, sim.squid.y)
    sim._act_on_neural_decision("exploring")
    assert sim.stats["shelter_arrivals"] == 0
    assert sim.stats["shelter_relief"] == 0.0

    # Reset body to exactly the same starting location, now actually
    # choose shelter. The first neural action causes approach, not instant
    # invisible relief; only a physical arrival relieves anxiety.
    sim.squid.x, sim.squid.y = before
    sim._act_on_neural_decision("approaching_plant")
    assert sim.stats["shelter_approaches"] == 1
    assert sim.stats["shelter_arrivals"] == 0
    assert sim.squid.anxiety == 90
    sim._act_on_neural_decision("approaching_plant")
    assert sim.stats["shelter_arrivals"] == 1
    assert sim.stats["shelter_relief"] == 16
    assert sim.squid.anxiety == 74
    assert math.hypot(sim.squid.x - .70, sim.squid.y - .50) < .085


def test_empty_or_out_of_sight_plant_world_never_grants_relief():
    for plants in ([], [{"x": .99, "y": .99}]):
        sim = aquarium()
        sim.set_plants(plants)
        sim.squid.anxiety = 90
        original = (sim.squid.x, sim.squid.y)
        for _ in range(10):
            sim._act_on_neural_decision("approaching_plant")
        assert (sim.squid.x, sim.squid.y) == original
        assert sim.squid.anxiety == 90
        assert sim.stats["shelter_arrivals"] == 0
        assert sim.stats["shelter_relief"] == 0


def test_nearby_plant_by_itself_is_not_free_mental_health_reward():
    sim = aquarium()
    sim.set_plants([{"x": .51, "y": .50}])
    sim.squid.anxiety = 90
    assert sim.squid.plant_nearby
    for i in range(25):
        sim.tick = i
        sim._simulation_step()
    assert sim.stats["shelter_arrivals"] == 0
    assert sim.stats["shelter_relief"] == 0.0


def test_plant_proximity_tracks_position_in_spatial_world():
    sim = aquarium()
    sim.set_plants([{"x": .70, "y": .50}])
    assert not sim.squid.plant_nearby
    sim._act_on_neural_decision("approaching_plant")
    assert not sim.squid.plant_nearby
    sim._act_on_neural_decision("approaching_plant")
    assert sim.squid.plant_nearby
    sim.set_plants([])
    assert not sim.squid.plant_nearby


def test_spatial_plants_remain_opt_in_for_baseline():
    sim = aquarium()
    assert sim.plant_items is None
    assert sim.squid.plant_nearby is False
