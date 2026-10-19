"""Android adapter regressions against the actual shared desktop core."""
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from dosidicus_mobile.engine import Simulation, Squid, NeuralBrain, Personality
from dosidicus_mobile.engine.brain_io import normalise_brain, import_brain, export_brain
from dosidicus_mobile.engine.portability import export_squid, import_squid, _brain_state_desktop
from src.portable_brain import HeadlessBrain, TrainingConfig
from src.brain_constants import ACTION_NEURONS, INNATE_ACTION_WIRING, REQUIRED_NEURONS
from src.decision_engine import select_action
from src.propagation import baseline_of


def test_newborn_has_desktop_structure_and_directed_synapses():
    mobile = NeuralBrain()
    desktop = HeadlessBrain()
    assert mobile.positions == desktop.positions
    assert mobile.weights == desktop.weights
    assert set(ACTION_NEURONS) <= mobile.state.keys()
    mobile.set_weight('hunger', 'act_eat', -.6)
    mobile.set_weight('act_eat', 'hunger', .2)
    assert mobile.get_weight('hunger', 'act_eat') == -.6
    assert mobile.get_weight('act_eat', 'hunger') == .2


def test_propagation_matches_desktop_for_imported_directed_network():
    mobile = NeuralBrain()
    desktop = HeadlessBrain()
    for name in ('act_eat', 'act_flee', 'act_play'):
        mobile.state[name] = desktop.state[name] = 0.0
    desktop.weights[('can_see_food', 'act_play')] = .73
    desktop.weights[('hunger', 'act_eat')] = -.42
    mobile.weights = dict(desktop.weights)
    for i in range(30):
        inputs = {'hunger': 25 + i, 'can_see_food': 100 if i % 3 else 0,
                  'is_startled': 100 if i == 20 else 0}
        mobile.propagate(inputs)
        desktop.update_state(inputs)
        desktop.propagate()
        assert mobile.state == desktop.state


def test_plasticity_matches_desktop_signed_updates():
    mobile = NeuralBrain()
    desktop = HeadlessBrain(mobile.config)
    for i in range(90):
        inputs = {'hunger': 100 if i % 2 else 0, 'happiness': 0 if i % 2 else 100,
                  'curiosity': 100 if i % 2 else 0}
        for brain in (mobile, desktop):
            brain.advance_clock()
            brain.update_state(inputs)
            brain.observe_for_learning()
        if i % 10 == 9:
            mobile.perform_hebbian_learning()
            desktop.perform_hebbian_learning()
    assert mobile.weights == desktop.weights
    assert min(mobile.get_weight('hunger', 'happiness'), mobile.get_weight('happiness', 'hunger')) < 0
    assert mobile.ledger.to_dict()['total_changes'] > 0


def test_event_counter_cannot_force_neurogenesis():
    brain = NeuralBrain()
    brain.neurogenesis['reward_counter'] = 999
    brain.sim_time = 200
    assert brain.check_neurogenesis({}, 200) is None


def test_neurogenesis_uses_shared_creator_and_persists():
    brain = NeuralBrain()
    name = brain._create_neuron('novelty', {})
    assert name in brain.positions
    restored = NeuralBrain.from_dict(brain.to_dict())
    assert restored.weights == brain.weights
    assert restored.enhanced_neurogenesis.functional_neurons[name].to_dict() == brain.enhanced_neurogenesis.functional_neurons[name].to_dict()


@pytest.mark.parametrize('personality', list(Personality))
def test_decision_uses_only_network_actions(personality):
    squid = Squid(personality)
    squid._last_dt = .1
    squid.hunger = 100
    squid.sleepiness = 100
    state = {n: 0.0 for n in squid.brain.state}
    state['act_play'] = 99
    expected, _, _ = select_action(state, jitter=False)
    squid.decide(state, [])
    assert expected == squid.last_decision['chosen'] == 'playing'
    assert not squid.is_sleeping
    state['act_play'] = 0
    squid.decide(state, [])
    assert squid.last_decision['chosen'] == 'idle'


def test_silent_action_bank_cannot_eat_or_flee_or_ink():
    sim = Simulation()
    sim.squid.brain.weights.clear()
    for n in ACTION_NEURONS:
        sim.squid.brain.state[n] = 0
    sim.squid.hunger = 100
    sim.drop_food(x=sim.squid.x, y=sim.squid.y)
    assert not sim._try_eat()
    sim.startle()
    assert not sim.squid.is_fleeing
    assert not sim.ink_clouds


def test_neural_sleep_reflex_and_ink_binding():
    sim = Simulation()
    sim.squid.brain.state['act_collapse'] = 100
    sim.squid.brain.state['act_ink'] = 100
    sim.squid.brain.sim_time = 20
    for binding in sim.squid.brain._bindings:
        binding.probability = 1
    sim._process_neural_outputs()
    assert sim.squid.is_sleeping
    assert len(sim.ink_clouds) == 1
    sim._process_neural_outputs()
    assert len(sim.ink_clouds) == 1  # rising edge / cooldown respected


def test_frame_rate_does_not_change_neural_tick_count():
    a, b = NeuralBrain(), NeuralBrain()
    clamped = {'hunger': 60, 'can_see_food': 100}
    for _ in range(300):
        a.advance(1 / 30, clamped)
    for _ in range(600):
        b.advance(1 / 60, clamped)
    assert a.sim_time == b.sim_time == 10
    assert a.state == b.state
    assert a.weights == b.weights


def test_simulation_and_save_roundtrip(tmp_path):
    sim = Simulation()
    sim.drop_food()
    for _ in range(300):
        assert isinstance(sim.update(1 / 30), str)
    for name in sim.squid.CORE_STATS:
        assert 0 <= getattr(sim.squid, name) <= 100
    path = str(tmp_path / 'save/squid.json')
    sim.save(path)
    loaded = Simulation.load(path)
    assert loaded.squid.brain.state == sim.squid.brain.state
    assert loaded.squid.brain.weights == sim.squid.brain.weights
    assert loaded.squid.personality == sim.squid.personality


def test_mobile_json_loads_in_actual_desktop_loader(tmp_path):
    from src.custom_brain_loader import BrainLoader
    brain = NeuralBrain()
    brain.set_weight('hunger', 'act_play', -.72)
    brain.set_weight('act_play', 'hunger', .31)
    path = tmp_path / 'brain.json'
    export_brain(brain, path)
    data = json.loads(path.read_text())
    parsed = BrainLoader._parse(None, data)
    assert parsed['weights'] == brain.weights
    assert parsed['positions'] == brain.positions
    assert parsed['output_bindings'] == brain.output_bindings
    assert import_brain(path).weights == brain.weights


@pytest.mark.parametrize('format', ['designer', 'save', 'legacy_positions', 'arrows', 'layers'])
def test_desktop_brain_formats_roundtrip(format, tmp_path):
    b = NeuralBrain()
    original = b.to_dict()
    if format == 'save':
        data = _brain_state_desktop(b)
        data.pop('neurons'); data.pop('connections')
    elif format == 'legacy_positions':
        data = dict(positions={n: dict(x=p[0], y=p[1]) for n,p in b.positions.items()},
                    weights={f'{a},{c}': w for (a,c),w in b.weights.items()})
    elif format == 'arrows':
        data = dict(neurons=original['neurons'], connections={f'{a}->{c}': w for (a,c),w in b.weights.items()})
    elif format == 'layers':
        data = dict(layers=[{'neurons': b.neuron_names}], custom_connections=original['connections'])
    else:
        data = original
    path = tmp_path / 'desktop.json'
    path.write_text(json.dumps(data))
    restored = import_brain(path)
    assert restored.weights == b.weights
    assert set(restored.positions) == set(b.positions)


def test_provenance_binding_and_action_representations_survive_json(tmp_path):
    b = NeuralBrain()
    name = b._create_neuron('novelty', {})
    b.represent_action('playing', name)
    b.set_weight('hunger', name, -.73)
    b.output_bindings.append(dict(neuron_name=name, output_hook='neuron_output_sleep', threshold=65))
    path = tmp_path / 'brain.json'
    export_brain(b, path)
    restored = import_brain(path)
    assert restored.action_representations == b.action_representations
    assert restored.weights == b.weights
    assert restored.ledger.to_dict() == b.ledger.to_dict()
    assert any(x['neuron_name'] == name for x in restored.output_bindings)


def test_mobile_archive_is_desktop_shaped_and_lossless(tmp_path):
    import zipfile
    sim = Simulation()
    sim.squid.hunger = 83
    sim.squid.brain.set_weight('hunger', 'act_play', -.43)
    path = str(tmp_path / 'squid.zip')
    export_squid(sim, path)
    with zipfile.ZipFile(path) as z:
        game = json.loads(z.read('game_state.json'))
        brain = json.loads(z.read('brain_state.json'))
        assert game['squid']['hunger'] == 83
        assert len(brain['weights_list']) == len(sim.squid.brain.weights)
    restored = import_squid(path)
    assert restored.squid.brain.weights == sim.squid.brain.weights
    assert restored.squid.hunger == 83


def test_desktop_archive_import_keeps_direction_and_history(tmp_path):
    import zipfile
    sim = Simulation()
    sim.squid.brain.set_weight('hunger', 'act_eat', -.7)
    sim.squid.brain.set_weight('act_eat', 'hunger', .2)
    bs = _brain_state_desktop(sim.squid.brain)
    path = str(tmp_path / 'desktop.zip')
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('game_state.json', json.dumps({'squid': {'hunger': 87, 'personality': 'timid'}}))
        z.writestr('brain_state.json', json.dumps(bs))
    restored = import_squid(path)
    assert restored.squid.brain.weights == sim.squid.brain.weights
    assert restored.squid.hunger == 87
    assert restored.squid.personality == Personality.TIMID


@pytest.mark.parametrize('bad', [None, {}, {'neurons': {'broken': [0, 0]}}])
def test_invalid_brains_rejected(bad):
    with pytest.raises(ValueError):
        normalise_brain(bad)


def test_legacy_mobile_save_migrates_motor_bank():
    data = dict(neuron_positions={n: list(p) for n,p in REQUIRED_NEURONS.items()},
                state={'hunger': 81}, weights={'hunger|happiness': -.4}, neurogenesis={})
    brain = NeuralBrain.from_dict(data)
    assert set(ACTION_NEURONS) <= brain.positions.keys()
    assert brain.get_weight('hunger', 'happiness') == -.4
    assert brain.get_weight('can_see_food', 'act_eat') > 0
    assert brain.state['hunger'] == 81


def test_apk_staging_includes_identical_shared_engine(tmp_path):
    import importlib.util
    script = Path(__file__).resolve().parents[1] / 'prepare_apk.py'
    spec = importlib.util.spec_from_file_location('prepare_apk', script)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    staged = module.prepare(tmp_path)
    for name in module.SHARED_MODULES:
        assert (staged / 'src' / (name + '.py')).read_bytes() == (script.parents[1] / 'src' / (name + '.py')).read_bytes()
    # Launch outside the checkout with Qt and Kivy imports actively forbidden.
    code = '''import sys
class RejectUI:
 def find_spec(self, fullname, *args):
  if fullname.split('.')[0] in ('PyQt5', 'kivy'): raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, RejectUI())
from dosidicus_mobile.engine import Simulation
s=Simulation()
for _ in range(60): s.update(1/30)
assert s.squid.brain.sim_time == 2
assert s.squid.brain.plasticity.stdp is not None
assert 'PyQt5' not in sys.modules and 'kivy' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=staged,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_learned_synapses_change_physiology_in_opposite_directions():
    from src.propagation import compute_neural_modulation
    a, b = NeuralBrain(), NeuralBrain()
    a.weights.clear(); b.weights.clear()
    a.weights[('can_see_food', 'anxiety')] = .9
    b.weights[('can_see_food', 'anxiety')] = -.9
    for brain in (a, b):
        brain.state['can_see_food'] = 100
    assert a.compute_neural_modulation()['anxiety'] > 0
    assert b.compute_neural_modulation()['anxiety'] < 0
    assert a.compute_neural_modulation() == compute_neural_modulation(a.state, a.weights)
    for brain in (a, b):
        brain.state['can_see_food'] = 0
        assert brain.compute_neural_modulation()['anxiety'] == 0


def test_custom_neuron_output_controls_body_and_can_eat():
    sim = Simulation()
    brain = sim.squid.brain
    brain.positions['food_desire'] = (400, 600)
    brain.state['food_desire'] = 100
    brain.state['act_eat'] = 0
    brain.sim_time = 30
    brain.output_bindings.append(dict(neuron_name='food_desire', output_hook='neuron_output_seek_food', threshold=70))
    brain.install_bindings()
    sim.squid._last_dt = .1
    sim.drop_food(x=sim.squid.x, y=sim.squid.y)
    sim._process_neural_outputs()
    sim.squid.decide(brain.state, sim.food_items)
    assert sim.squid.last_decision['chosen'] == 'eating'
    assert sim._try_eat()


def test_mobile_memory_uses_desktop_core_without_disk_io():
    from dosidicus_mobile.engine.memory import MemoryManager
    from src.memory_manager import MemoryManager as DesktopMemory
    mobile = MemoryManager()
    desktop = DesktopMemory(persistent=False, clock=lambda: mobile._now)
    for i in range(3):
        mobile.add_short_term('food', 'sushi', 'Ate sushi', now=i)
        desktop.add_short_term_memory('food', 'sushi', 'Ate sushi')
    assert [(m['key'],m['importance']) for m in mobile.short_term] == [(m['key'],m['importance']) for m in desktop.short_term_memory]
    mobile.periodic(600)
    desktop.periodic_memory_management()
    assert len(mobile.short_term) == len(desktop.short_term_memory)


def test_loading_never_reclassifies_motor_neurons_as_grown():
    brain = NeuralBrain.from_dict(NeuralBrain().to_dict())
    assert not set(ACTION_NEURONS) & brain.enhanced_neurogenesis.functional_neurons.keys()
    assert not set(ACTION_NEURONS) & set(brain.neurogenesis_data['new_neurons'])


def test_actual_desktop_loader_restores_mobile_cognitive_history(tmp_path):
    from src.custom_brain_loader import BrainLoader
    from types import SimpleNamespace
    mobile = NeuralBrain()
    name = mobile._create_neuron('novelty', {})
    mobile.represent_action('playing', name)
    mobile.set_weight('hunger', name, -.51)
    path = tmp_path / 'mobile-brain.json'
    export_brain(mobile, path)
    payload = json.loads(path.read_text())
    desktop = HeadlessBrain()
    loader = SimpleNamespace(brain_widget=desktop)
    parsed = BrainLoader._parse(loader, payload)
    BrainLoader._apply(loader, parsed)
    assert desktop.weights == mobile.weights
    assert desktop.action_representations == mobile.action_representations
    assert desktop.ledger.to_dict() == mobile.ledger.to_dict()
    assert desktop.enhanced_neurogenesis.functional_neurons[name].strength_multiplier == mobile.enhanced_neurogenesis.functional_neurons[name].strength_multiplier


def test_achievement_definitions_match_desktop():
    from dosidicus_mobile.engine.achievements import ACHIEVEMENTS
    from plugins.achievements.achievements_data import ACHIEVEMENT_DEFINITIONS
    assert ACHIEVEMENTS.keys() == ACHIEVEMENT_DEFINITIONS.keys()
    for key, definition in ACHIEVEMENT_DEFINITIONS.items():
        assert ACHIEVEMENTS[key].target_count == definition.target_count
        assert ACHIEVEMENTS[key].points == definition.points


def test_brain_save_imports_boolean_sensors_at_full_scale():
    brain = NeuralBrain()
    payload = _brain_state_desktop(brain)
    payload['neuron_states']['is_startled'] = True
    restored = NeuralBrain.from_dict(payload)
    assert restored.state['is_startled'] == 100


def test_visitor_uses_imported_brain_instead_of_scripted_looting():
    sim = Simulation()
    guest = Simulation()
    guest.squid.brain.weights.clear()
    guest.squid.brain.state.update({name: 0 for name in ACTION_NEURONS})
    sim.drop_food(x=400, y=300)
    visitor = sim.add_visitor(guest.to_dict(), name='Quiet guest')
    for _ in range(120):
        sim._update_visitors(1 / 30)
    assert visitor['stole'] == 0
    assert not visitor['wants_rock']
    assert not sim.ink_clouds
    assert sim._visitor_minds[visitor['id']].last_decision['chosen'] == 'exploring'


def test_clock_transfer_preserves_deficit_age_and_spike_intervals():
    from src.brain_clock import rebase_cognitive_state
    data = {'clock': {'now': 1000}, 'capability': {'active': [dict(first_seen=940., last_seen=990.)]},
            'plasticity': {'stdp': {'spike_tracker': {'spike_history': {'a': [dict(timestamp=999.)], 'b': [dict(timestamp=999.8)]}},
                                  'eligibility_traces': {'a|b': dict(trace=.7, time=999.5)}}}}
    moved = rebase_cognitive_state(data, 50)
    deficit = moved['capability']['active'][0]
    assert deficit['last_seen'] - deficit['first_seen'] == 50
    stdp = moved['plasticity']['stdp']
    assert stdp['spike_tracker']['spike_history']['a'][0]['timestamp'] == 49
    assert stdp['eligibility_traces']['a|b']['time'] == 49.5
    assert data['clock']['now'] == 1000  # caller's data is never mutated


def test_import_brain_keeps_current_pet_clock(tmp_path):
    brain = NeuralBrain(); brain.sim_time = 500
    path = tmp_path / 'brain.json'
    export_brain(brain, path)
    restored = import_brain(path, sim_time=1200)
    assert restored.sim_time == 1200
    assert restored.weights == brain.weights


def test_imported_desktop_actuators_control_the_mobile_body():
    sim = Simulation()
    squid = sim.squid
    squid.anxiety = 60
    squid.curiosity = 40
    squid.is_fleeing = squid.is_startled = True
    sim._fire_output('neuron_output_calm', 100, {})
    assert squid.anxiety == 50
    assert not squid.is_fleeing and not squid.is_startled
    sim._fire_output('neuron_output_boost_curiosity', 80, {})
    assert squid.curiosity == 44
    sim._fire_output('neuron_output_change_color', 100, {'red': 255, 'green': 128, 'blue': 0})
    assert squid.color_tint == (1, 128 / 255, 0)
    sim.add_decoration('rock01.png', 'rock', squid.x, squid.y)
    sim._fire_output('neuron_output_pick_up_rock', 100, {})
    assert squid.carrying_rock
    carried_id = squid.carried_rock_id
    sim._fire_output('neuron_output_throw_rock', 100, {})
    assert not squid.carrying_rock
    assert carried_id in sim._rock_velocities


def test_mobile_fight_brings_the_pair_together_before_the_shared_cloud_phase(monkeypatch):
    sim = Simulation()
    visitor = sim.add_visitor(Simulation().to_dict(), name='Guest')
    visitor['personality'] = 'adventurous'
    visitor['x'], visitor['y'] = sim.squid.x+110, sim.squid.y
    sim._start_fight(visitor)
    fight = sim.fight
    sim._start_fight(visitor)
    assert sim.fight is fight
    assert fight['phase'] == 'approaching'
    # Measure the approach without the later grapple's random jitter.
    monkeypatch.setattr(random, 'uniform', lambda low, high: 0.)
    for _ in range(30):
        sim._update_fight(1/30)
        if fight['phase'] == 'fighting':
            break
    assert fight['phase'] == 'fighting'
    assert abs(sim.squid.x-visitor['x']) <= 40
