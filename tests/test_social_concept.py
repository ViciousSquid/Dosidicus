"""First peer perception grows an enduring concept linked to anxiety, with its cause."""
import sys
from pathlib import Path

import pytest

from src.brain_constants import unregister_input_sensor, is_learning_target
from src.portable_brain import HeadlessBrain, TrainingConfig


@pytest.fixture(autouse=True)
def isolated_sensor():
    from src.brain_constants import registered_input_sensors, register_input_sensor
    previous = registered_input_sensors().get('conspecific_visible')
    yield
    unregister_input_sensor('conspecific_visible')
    if previous:
        register_input_sensor('conspecific_visible', **previous, position=(350, 50))


@pytest.mark.parametrize('chosen', ['social', 'encounter'])
def test_first_sighting_has_a_real_neuron_and_exact_provenance(chosen, monkeypatch):
    monkeypatch.setattr('src.neurogenesis.random.choice', lambda names: chosen)
    brain = HeadlessBrain()
    growth = brain.enhanced_neurogenesis
    assert growth.observe_social(0) is None
    assert chosen not in brain.positions
    # First encounters must work even at a configured growth cap/cooldown.
    growth.config.neurogenesis['max_neurons'] = len(brain.positions)
    growth.config.neurogenesis['max_per_type'] = {'novelty': 0}
    growth._last_growth_at = 10_000
    name = growth.observe_social(100.)
    assert name == chosen
    assert growth.functional_neurons[name].display_name == chosen.title()
    assert is_learning_target(name)
    assert brain.weights['conspecific_visible', name] > 0
    assert brain.weights[name, 'anxiety'] > 0
    assert ('anxiety', name) not in brain.weights
    assert brain.weights[name, 'curiosity'] == 0
    origin = brain.ledger.origins[name]
    assert origin.deficit_summary == 'Other squid encountered!'
    assert origin.evidence['concept'] == 'social'
    assert origin.evidence['conspecific_visible'] == 100
    assert 'Other squid encountered!' in origin.describe()
    assert origin.wiring
    assert growth.observe_social(100.) is None
    assert growth.observe_social(0.) is None
    brain.propagate()
    present = brain.state[name]
    assert present > 50
    assert brain.compute_neural_modulation()['anxiety'] > 0
    assert (name, 'anxiety', .3, 'remedy') in origin.wiring
    brain.state['conspecific_visible'] = 0.
    for _ in range(10):
        brain.propagate()
    assert brain.state[name] < present
    assert name in brain.positions
    assert growth.intelligent_pruning() != name


def test_concept_and_cause_survive_a_fresh_trainer_import():
    brain = HeadlessBrain()
    name = brain.enhanced_neurogenesis.observe_social(100.)
    data = brain.export_brain()
    unregister_input_sensor('conspecific_visible')
    loaded = HeadlessBrain()
    assert loaded.load_brain(data)
    assert not is_learning_target('conspecific_visible')
    assert loaded.enhanced_neurogenesis.functional_neurons[name].represents_concept == 'social'
    assert loaded.ledger.origins[name].deficit_summary == 'Other squid encountered!'
    assert loaded.enhanced_neurogenesis.observe_social(100.) is None
    loaded.state['conspecific_visible'] = 0.
    loaded.state[name] = 50.
    loaded.propagate()
    assert loaded.state['conspecific_visible'] == 0.
    assert loaded.state[name] == pytest.approx(50.)


def test_mobile_grows_only_for_an_on_screen_squid_and_remembers(tmp_path):
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    sim = Simulation()
    sim._fight_cooldown = 100.
    visitor = sim.add_visitor(Simulation().to_dict(), name='Visitor')
    visitor['x'], visitor['y'] = -300., 200.
    sim.update(1.)
    assert not any(n.represents_concept for n in sim.squid.brain.enhanced_neurogenesis.functional_neurons.values())
    visitor['x'], visitor['y'] = 400., 200.
    sim.update(1.)
    records = sim.squid.brain.enhanced_neurogenesis.functional_neurons
    concepts = [n for n, fn in records.items() if fn.represents_concept == 'social']
    assert len(concepts) == 1
    name = concepts[0]
    assert sim.newborn_neuron == name
    visitor_mind = sim._visitor_minds[visitor['id']].brain
    assert any(fn.represents_concept == 'social' for fn in visitor_mind.enhanced_neurogenesis.functional_neurons.values())
    path = tmp_path / 'pet.zip'
    sim.save(path)
    restored = Simulation.load(path)
    assert restored.squid.brain.ledger.origins[name].deficit_summary == 'Other squid encountered!'
    restored.update(1.)
    assert restored.squid.brain.state['conspecific_visible'] == 0.
    assert restored.squid.brain.enhanced_neurogenesis.observe_social(100.) is None


def test_lifetime_without_peers_never_grows_the_concept():
    brain = HeadlessBrain()
    brain.enhanced_neurogenesis.attach_social_sensor()
    for _ in range(120):
        brain.state['conspecific_visible'] = 0.
        brain.propagate()
    assert not any(fn.represents_concept for fn in brain.enhanced_neurogenesis.functional_neurons.values())
    assert not {'social', 'encounter'} & set(brain.positions)


def test_desktop_off_screen_presence_does_not_count_as_an_encounter():
    from plugins.multiplayer.encounter_sensors import ConspecificView, EncounterSensors
    from plugins.multiplayer.identity import SquidIdentity
    view = ConspecificView()
    identity = SquidIdentity('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
    view.observe_peer(identity, x=-100, y=100, observer_x=400, observer_y=100)
    senses = EncounterSensors(view, bounds=(900, 500))
    brain = HeadlessBrain()
    assert senses.visible() == 0
    assert brain.enhanced_neurogenesis.observe_social(senses.visible()) is None
    view.observe_peer(identity, x=100, y=100, observer_x=400, observer_y=100)
    assert senses.visible() == 100
    assert brain.enhanced_neurogenesis.observe_social(senses.visible()) in ('social', 'encounter')
