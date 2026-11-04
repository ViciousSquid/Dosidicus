"""Neural motor exploration must learn only from actual causal outcomes.

No Qt or display required; all tests use real HeadlessBrain, ActionOutcomeLedger
and the production decision engine. Teaching is disabled by default.
"""
from headless.headless_trainer import HeadlessSimulation
from src.action_discovery import ActionDiscovery
from src.brain_constants import ACTION_THRESHOLDS, LEARNED_ACTIONS
from src.portable_brain import HeadlessBrain, TrainingConfig


def brain():
    return HeadlessBrain(TrainingConfig(seed=21, neurogenesis_enabled=False))


def settle_trial(b, learner, *, action="sleeping", neuron="act_rest",
                 sleepy_before=94.0, sleepy_after=65.0, moment=10.0):
    """An experimentally observed action and its delayed physiological result.

    The outcome ledger really settles the event. No outcomes are fabricated
    inside ActionDiscovery; only the body's observed before/after state is
    supplied to ActionOutcomeLedger.
    """
    state = dict(b.state)
    state["sleepiness"] = sleepy_before
    episode_id = b.causal_learning.on_action(action, state, now=moment)
    assert episode_id is not None
    learner.committed(episode_id, neuron, action, state)
    later = dict(state)
    later["sleepiness"] = sleepy_after
    result = b.causal_learning.on_tick(later, now=moment + 7.0)
    assert len(result) == 1
    assert result[0].episode_id == episode_id
    learner.process_closed()


def test_newborn_learned_motors_have_no_positive_drivers():
    b = brain()
    for motor in ("act_play", "act_shelter", "act_rest"):
        assert motor in LEARNED_ACTIONS
        assert not any(dst == motor and w > 0 for (src, dst), w in b.weights.items())


def test_no_spontaneous_discovery_by_default_or_in_frozen_evaluation():
    ordinary = HeadlessSimulation(TrainingConfig(seed=11,
        learning_enabled=True, action_discovery_rate=0,
        food_spawn_chance=0, startle_chance=0))
    frozen = HeadlessSimulation(TrainingConfig(seed=11,
        learning_enabled=False, action_discovery_rate=1,
        food_spawn_chance=0, startle_chance=0))
    assert ordinary.action_discovery is None
    assert frozen.action_discovery is None


def test_babbling_is_a_motor_spike_not_an_explicit_action_policy():
    b = brain()
    learner = ActionDiscovery(b, rate=1.0, seed=3)
    state = dict(b.state)
    for key in ("act_flee", "act_eat", "act_collapse"):
        state[key] = 0.0
    motor = learner.excite(state)
    assert motor in {"act_play", "act_shelter", "act_rest"}
    assert state[motor] == 96.0
    assert learner.statistics()["motor_probes"] == 1
    # Excitation alone neither creates a synapse nor declares an outcome.
    assert not any(dst == motor and w > 0 for (src, dst), w in b.weights.items())
    assert learner.executed_probes == 0


def test_urgent_neural_threat_prevents_random_motor_trial():
    b = brain()
    learner = ActionDiscovery(b, rate=1.0, seed=3)
    state = dict(b.state)
    state["act_flee"] = ACTION_THRESHOLDS["act_flee"] + 10
    assert learner.excite(state) is None
    assert learner.probes == 0


def test_motor_trial_with_no_reward_creates_no_skill_connection():
    b = brain()
    learner = ActionDiscovery(b, rate=0.0)
    for i in range(5):
        settle_trial(b, learner, action="playing", neuron="act_play",
                     sleepy_before=90, sleepy_after=90, moment=10 + i * 10)
    assert learner.trials_closed == 5
    assert learner.connections_taught == 0
    assert ("sleepiness", "act_play") not in b.weights


def test_positive_repeated_outcomes_build_a_directed_skill_synapse():
    b = brain()
    learner = ActionDiscovery(b, rate=0.0)
    for i in range(6):
        settle_trial(b, learner, moment=10 + i * 10)
    edge = ("sleepiness", "act_rest")
    assert b.weights.get(edge, 0.0) > 0
    assert learner.trials_closed == 6
    assert learner.connections_taught >= 1
    events = [e for e in b.ledger.weight_history(edge, limit=30)
              if e.mechanism == "causal_motor_discovery"]
    assert events
    assert all(e.episode_id is not None for e in events)
    assert all(e.edge == edge for e in events)


def test_external_reward_interrupts_learning_and_cleans_pending_trials():
    b = brain()
    learner = ActionDiscovery(b, rate=0.0)
    state = dict(b.state)
    state["sleepiness"] = 95.0
    episode_id = b.causal_learning.on_action("sleeping", state, now=1.0)
    learner.committed(episode_id, "act_rest", "sleeping", state)
    assert episode_id in learner.pending
    b.causal_learning.discard_pending_outcomes(reason="scripted_feed")
    assert learner.process_closed() == 0
    assert not learner.pending
    assert learner.aborted_trials == 1
    assert learner.connections_taught == 0


def test_probing_without_teaching_never_creates_pending_attribution():
    b = brain()
    learner = ActionDiscovery(b, rate=1.0, seed=1, teaching=False)
    learner.committed("id123", "act_rest", "sleeping", dict(b.state))
    assert learner.executed_probes == 1
    assert learner.pending == {}
    assert learner.process_closed() == 0
    assert learner.connections_taught == 0


def test_weak_learned_motor_pathway_does_not_stop_exploration():
    b = brain()
    for neuron in ("act_play", "act_shelter"):
        b.apply_weight_change(("sleepiness", neuron), value=0.90,
                              mechanism="test")
    b.apply_weight_change(("sleepiness", "act_rest"), value=0.40,
                          mechanism="test")
    learner = ActionDiscovery(b, rate=1.0, seed=42)
    state = dict(b.state)
    # Only at high fatigue can a 0.90 synapse carry sufficient activation.
    state["sleepiness"] = 95.0
    for key in ("act_flee", "act_eat", "act_collapse"):
        state[key] = 0.0
    assert learner.excite(state) == "act_rest"


def test_real_headless_integration_executes_opt_in_motor_trial():
    sim = HeadlessSimulation(TrainingConfig(
        seed=31, learning_enabled=True, neurogenesis_enabled=False,
        action_discovery_rate=1.0, food_spawn_chance=0,
        startle_chance=0, poop_spawn_chance=0))
    sim.tick = 0
    sim._simulation_step()
    assert sim.action_discovery.probes == 1
    assert sim.action_discovery.executed_probes == 1
    assert any(sim.stats["actions_selected"].get(action, 0) == 1
               for action in ("sleeping", "approaching_plant", "playing"))
    assert not sim.action_discovery.connections_taught
