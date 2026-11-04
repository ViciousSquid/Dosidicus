"""Headless trainer must learn from its own actions, not random body rewards.

These integration tests use the real HeadlessBrain + shared decision engine.
The only mocked methods are isolated *actuator* unit cases.
"""
import random

from headless.headless_trainer import HeadlessSimulation
from src.portable_brain import TrainingConfig


def sim(seed=19, **overrides):
    return HeadlessSimulation(TrainingConfig(
        seed=seed, learning_enabled=False, neurogenesis_enabled=False,
        food_spawn_chance=0, poop_spawn_chance=0, startle_chance=0,
        **overrides,
    ))


def test_food_never_disappears_or_feeds_without_neural_action():
    tank = sim()
    tank.food_items = [{"x": 0.5, "y": 0.5}]
    tank.brain.remove_weight(("can_see_food", "act_eat"),
                             mechanism="test", reason="disable food reflex")
    tank.brain.remove_weight(("hunger", "act_eat"),
                             mechanism="test", reason="disable hunger reflex")
    for i in range(25):
        tank.tick = i
        tank._simulation_step()
    assert tank.stats["food_eaten"] == 0
    assert len(tank.food_items) == 1
    assert tank.stats["actions_selected"].get("eating", 0) == 0


def test_real_newborn_can_seek_and_consume_food_with_its_action_neuron():
    tank = sim()
    tank.food_items = [{"x": 0.54, "y": 0.5}]
    for i in range(100):
        tank.tick = i
        tank._simulation_step()
        if tank.stats["food_eaten"]:
            break
    assert tank.stats["food_eaten"] == 1, tank.stats
    assert tank.stats["actions_selected"].get("eating", 0) > 0
    assert not tank.food_items
    assert tank.squid.is_eating
    assert tank.squid.hunger < 50 + (i + 1) * 0.1


def test_food_outside_sight_does_not_activate_the_food_sensor():
    tank = sim()
    tank.food_items = [{"x": 0.99, "y": 0.99}]
    tank._refresh_food_sense()
    assert tank.squid.food_visible is False
    assert tank._nearest_visible_food() is None
    tank.tick = 0
    tank._simulation_step()
    assert tank.stats["food_eaten"] == 0


def test_blank_control_has_no_innate_motor_or_free_food():
    tank = HeadlessSimulation(TrainingConfig(
        seed=19, blank=True, learning_enabled=False,
        food_spawn_chance=0, poop_spawn_chance=0, startle_chance=0,
    ))
    initial = (tank.squid.x, tank.squid.y)
    tank.food_items = [{"x": 0.5, "y": 0.5}]
    for i in range(20):
        tank.tick = i
        tank._simulation_step()
    assert tank.stats["food_eaten"] == 0
    assert (tank.squid.x, tank.squid.y) == initial
    assert tank.stats["actions_selected"].get("idle", 0) == 20


def test_external_feeding_is_not_claimed_as_network_success():
    tank = sim()
    tank.tick = 0
    tank._execute_event({"type": "feed"})
    assert tank.stats["manual_feedings"] == 1
    assert tank.stats["food_eaten"] == 0


def test_frozen_evaluation_does_not_modify_weights_or_learning_ledger():
    tank = sim()
    before = dict(tank.brain.weights)
    for i in range(45):
        tank.tick = i
        tank._simulation_step()
    assert dict(tank.brain.weights) == before
    assert tank.stats["hebbian_updates"] == 0
    assert tank.stats["neurons_created"] == 0
    assert tank.brain.causal_learning.closed_episodes == 0


def test_selected_flight_not_a_world_event_causes_escape():
    tank = sim()
    tank.squid.startle()
    assert tank.squid.is_fleeing is False
    # Make the brain desire flight, while keeping the real selection logic.
    tank.brain.state["act_flee"] = 100.0
    tank.brain.state["act_eat"] = 0.0
    tank.squid.update = lambda dt=1.: None
    tank._update_environment = lambda: None
    tank.brain.propagate = lambda observe_learning=True: None
    tank.tick = 0
    tank._simulation_step()
    assert tank.stats["escaped_startles"] == 1
    assert tank.stats["flee_actions"] == 1
    assert tank.squid.is_startled is False
    assert tank.squid.is_fleeing is True


def test_headless_training_same_seed_same_behavioural_outcomes():
    first = sim(seed=321)
    second = sim(seed=321)
    for tank in (first, second):
        # Reset the global RNG to reproduce the same full trajectory.
        random.seed(321)
        tank.run(ticks=150, progress_interval=0)
    fields = ("food_eaten", "manual_feedings", "food_approaches",
              "escaped_startles", "actions_selected")
    assert {k: first.stats[k] for k in fields} == {
        k: second.stats[k] for k in fields}


def test_manual_feed_interrupts_only_pending_credit_not_settled_learning():
    tank = sim()
    ledger = tank.brain.causal_learning
    ledger.on_action("exploring", tank.brain.state)
    assert len(ledger._open) == 1
    before = dict(tank.brain.weights)
    tank.tick = 0
    tank._execute_event({"type": "feed"})
    assert not ledger._open
    assert ledger.current_action == ""
    assert tank.stats["manual_feedings"] == 1
    assert tank.stats["food_eaten"] == 0
    assert dict(tank.brain.weights) == before
    ledger.on_action("exploring", tank.brain.state)
    assert len(ledger._open) == 1
    tank._execute_event({"type": "set_state", "state": {"hunger": 10}})
    assert not ledger._open


def test_neurally_earned_food_does_not_discard_its_outcome_window():
    tank = sim()
    ledger = tank.brain.causal_learning
    tank.food_items = [{"x": 0.5, "y": 0.5}]
    tank._refresh_food_sense()
    ledger.on_action("eating", tank.brain.state)
    assert len(ledger._open) == 1
    tank._act_on_neural_decision("eating")
    assert tank.stats["food_eaten"] == 1
    assert len(ledger._open) == 1, (
        "a real action must keep its causal learning window")
