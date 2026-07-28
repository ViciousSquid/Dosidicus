"""Engine smoke tests. Run: python -m pytest android/tests  (or python this file)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dosidicus_mobile.engine import Simulation, Squid, NeuralBrain, Personality


def test_brain_defaults():
    b = NeuralBrain(Personality.ADVENTUROUS)
    assert set(["hunger", "happiness", "curiosity", "can_see_food"]).issubset(b.state)
    assert b.get_weight("hunger", "satisfaction") == b.get_weight("satisfaction", "hunger")


def test_hebbian_strengthens_coactive_neurons():
    b = NeuralBrain(Personality.ADVENTUROUS)
    b.state["curiosity"] = 90.0
    b.state["happiness"] = 90.0
    before = b.get_weight("curiosity", "happiness")
    for _ in range(50):
        b.hebbian_step()
    after = b.get_weight("curiosity", "happiness")
    assert after > before, "co-active neurons should wire together"
    assert -1.0 <= after <= 1.0


def test_weight_decay_relaxes_idle_links():
    b = NeuralBrain(Personality.ADVENTUROUS)
    b.set_weight("hunger", "curiosity", 0.5)
    for name in b.state:
        b.state[name] = 0.0  # nothing co-active
    for _ in range(100):
        b.hebbian_step()
    assert abs(b.get_weight("hunger", "curiosity")) < 0.5


def test_neurogenesis_grows_neuron():
    b = NeuralBrain(Personality.ADVENTUROUS)
    b.sim_time = 100.0  # past the cooldown on the internal clock
    b.neurogenesis["reward_counter"] = 999
    born = b.check_neurogenesis()
    assert born is not None
    assert born in b.neuron_positions
    assert born in b.state
    # new neuron wired to the whole network
    assert b.get_weight(born, "satisfaction") != 0.0


def test_feeding_reduces_hunger_and_learns():
    s = Squid(Personality.GREEDY)
    s.hunger = 80.0
    w_before = s.brain.get_weight("hunger", "satisfaction")
    s.feed("sushi")
    assert s.hunger < 80.0
    assert s.brain.get_weight("hunger", "satisfaction") > w_before


def test_simulation_runs_and_is_stable():
    sim = Simulation()
    sim.drop_food()
    for _ in range(300):  # ~10s at 30fps
        status = sim.update(1 / 30.0)
        assert isinstance(status, str)
    for name in sim.squid.CORE_STATS:
        v = getattr(sim.squid, name)
        assert 0.0 <= v <= 100.0, f"{name} out of range: {v}"


def test_save_load_roundtrip():
    sim = Simulation()
    sim.drop_food()
    for _ in range(60):
        sim.update(1 / 30.0)
    # force a grown neuron so we exercise dynamic-neuron persistence
    sim.squid.brain.sim_time = 100.0
    sim.squid.brain.neurogenesis["novelty_counter"] = 999
    assert sim.squid.brain.check_neurogenesis() is not None

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "save", "squid.json")
        sim.save(path)
        loaded = Simulation.load(path)

    assert loaded.squid.personality == sim.squid.personality
    assert abs(loaded.squid.hunger - sim.squid.hunger) < 1e-6
    assert loaded.squid.brain.neuron_names == sim.squid.brain.neuron_names
    for pair, w in sim.squid.brain.weights.items():
        assert abs(loaded.squid.brain.get_weight(*pair) - w) < 1e-6


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} engine tests passed.")


if __name__ == "__main__":
    _run_all()
