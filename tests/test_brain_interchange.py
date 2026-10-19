"""Exercise real file APIs across mobile, desktop, Designer and CLI training."""
import copy
import json
from pathlib import Path
import sys
import zipfile

import pytest
from PyQt5 import QtWidgets

sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
from dosidicus_mobile.engine import NeuralBrain, Simulation
from dosidicus_mobile.engine.brain_io import export_brain, import_brain
from dosidicus_mobile.engine.portability import export_squid, import_squid
from src.brain_io import normalise_brain, read_brain_file
from src.designer_core import BrainDesign
from src.portable_brain import HeadlessBrain, TrainingConfig
from src.brain_tool import SquidBrainWindow
from src.brain_widget import BrainWidget
from src.custom_brain_loader import BrainLoader
from src.config_manager import ConfigManager
from src.save_manager import SaveManager
from src.brain_constants import CORE_STAT_NEURONS


@pytest.fixture
def desktop():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    brain = BrainWidget(config=ConfigManager())
    brain._cleanup_render_worker()
    for name in ('neurogenesis_timer', 'animation_timer', '_render_timer', '_brain_export_timer', '_link_fade_timer'):
        timer = getattr(brain, name, None)
        if timer is not None:
            timer.stop()
    window = SquidBrainWindow.__new__(SquidBrainWindow)
    window.brain_widget = brain
    window.config = brain.config
    window.tamagotchi_logic = None
    window.debug_mode = False
    yield window
    brain.stop_worker()
    brain._cleanup_render_worker()
    brain.deleteLater()
    app.processEvents()


@pytest.fixture
def specimen():
    brain = NeuralBrain()
    name = brain._create_neuron('novelty', {})
    brain.state[name] = 73
    brain.state['can_see_food'] = 100
    brain.set_weight('hunger', name, -.73)
    brain.set_weight(name, 'hunger', .24)
    brain.represent_action('playing', name)
    brain.output_bindings.append(dict(neuron_name=name, output_hook='neuron_output_change_color',
                                     threshold=65, hook_params=dict(red=100, green=200, blue=255)))
    brain.install_bindings()
    brain._brain_document = {'future_extension': {'note': 'preserve through every editor'}}
    return brain


def assert_same_brain(actual, expected):
    actual, expected = normalise_brain(actual), normalise_brain(expected)
    assert {n: nd['position'] for n, nd in actual['neurons'].items()} == {n: nd['position'] for n, nd in expected['neurons'].items()}
    assert {(e['source'], e['target']): e['weight'] for e in actual['connections']} == {(e['source'], e['target']): e['weight'] for e in expected['connections']}
    assert actual['output_bindings'] == expected['output_bindings']
    assert actual['action_representations'] == expected['action_representations']
    assert actual['provenance'] == expected['provenance']
    assert actual['future_extension'] == expected['future_extension']
    for name in expected['functional_neurons']:
        assert actual['enhanced_neurogenesis']['functional_neurons'][name] == expected['enhanced_neurogenesis']['functional_neurons'][name]


@pytest.mark.parametrize('producer', ['mobile', 'desktop_save', 'designer', 'designer_dosidicus', 'trainer'])
@pytest.mark.parametrize('consumer', ['mobile', 'desktop', 'designer', 'trainer'])
def test_every_producer_loads_in_every_consumer(producer, consumer, tmp_path, specimen, desktop):
    path = tmp_path / 'brain.json'
    source = specimen.to_dict()
    export_brain(specimen, path)
    if producer == 'desktop_save':
        loader = type('Loader', (), {'brain_widget': desktop.brain_widget})()
        BrainLoader._apply(loader, BrainLoader._parse(loader, read_brain_file(path)))
        saved = SquidBrainWindow.get_brain_state(desktop)
        manager = SaveManager(str(tmp_path / 'saves'))
        path = Path(manager.save_game({'brain_state': saved,
                    'game_state': {'squid': dict(uuid='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                                               **{n: source['state'][n] for n in CORE_STAT_NEURONS})}}))
    elif producer.startswith('designer'):
        design = BrainDesign.load(path)
        ok, message = design.save(str(path), format='dosidicus' if producer.endswith('dosidicus') else 'designer')
        assert ok, message
    elif producer == 'trainer':
        trainer = HeadlessBrain()
        assert trainer.load_brain_file(str(path))
        assert trainer.save_brain(str(path))
    if consumer == 'mobile':
        result = import_brain(path).to_dict()
    elif consumer == 'designer':
        result = BrainDesign.load(path).to_designer_format()
    elif consumer == 'trainer':
        brain = HeadlessBrain()
        assert brain.load_brain_file(str(path))
        result = brain.export_brain()
    else:
        SquidBrainWindow.set_brain_state(desktop, read_brain_file(path))
        result = SquidBrainWindow.get_brain_state(desktop)
    assert_same_brain(result, source)


def test_designer_saves_a_blank_brain_without_adding_synapses(tmp_path):
    brain = HeadlessBrain(TrainingConfig(blank=True))
    path = tmp_path / 'blank.json'
    assert brain.save_brain(path)
    design = BrainDesign.load(path)
    assert design.save(path)[0]
    restored = import_brain(path)
    assert not restored.weights
    assert restored.positions == brain.positions


def test_mobile_autosave_is_readable_by_the_desktop_save_manager(tmp_path):
    sim = Simulation()
    sim.squid.name = 'Inky'
    sim.squid.color_tint = (.2, .6, .8)
    sim.squid.hunger = 87
    path = tmp_path / 'autosave.zip'
    sim.save(path)
    saved = SaveManager(str(tmp_path))._load_single_save(path)
    assert set(('game_state', 'brain_state', 'statistics', 'ShortTerm', 'LongTerm', 'custom_brain')) <= saved.keys()
    assert saved['game_state']['squid']['name'] == 'Inky'
    assert saved['game_state']['squid']['hunger'] == 87
    assert saved['game_state']['squid']['tint_color'] == [51, 153, 204]
    assert saved['brain_state']['weights_list']
    restored = Simulation.load(path)
    assert restored.squid.name == 'Inky'
    assert restored.squid.color_tint == (.2, .6, .8)
    assert restored.squid.hunger == 87
    assert restored.squid.brain.weights == sim.squid.brain.weights


def test_desktop_edits_override_stale_mobile_extensions(tmp_path):
    sim = Simulation()
    path = tmp_path / 'edited.zip'
    export_squid(sim, path)
    with zipfile.ZipFile(path) as archive:
        entries = {n: archive.read(n) for n in archive.namelist()}
    brain = json.loads(entries['brain_state.json'])
    brain['weights_list'].append(['hunger', 'act_play', -.82])
    entries['brain_state.json'] = json.dumps(brain)
    game = json.loads(entries['game_state.json'])
    game['squid'].update(name='Desktop name', hunger=93, tint_color=[255, 128, 0])
    entries['game_state.json'] = json.dumps(game)
    with zipfile.ZipFile(path, 'w') as archive:
        for n, data in entries.items():
            archive.writestr(n, data)
    restored = import_squid(path)
    assert restored.squid.brain.get_weight('hunger', 'act_play') == -.82
    assert restored.squid.hunger == 93
    assert restored.squid.name == 'Desktop name'
    assert restored.squid.color_tint == (1, 128/255, 0)


def test_old_mobile_json_still_loads_and_next_save_is_desktop_zip(tmp_path):
    sim = Simulation()
    path = tmp_path / 'squid_save.json'
    path.write_text(json.dumps(sim.to_dict()))
    restored = Simulation.load(path)
    converted = tmp_path / 'squid_save.zip'
    restored.save(converted)
    assert zipfile.is_zipfile(converted)
    assert Simulation.load(converted).squid.uuid == sim.squid.uuid
