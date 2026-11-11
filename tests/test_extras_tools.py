"""The browser tools in extras/ keep in step with the game, and work offline.

They are single HTML pages and cannot import the game, so what they must
agree with it about is written for them by tools/update_extras_data.py. If
the game changes and that file is not rewritten, this fails.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRAS = ROOT / 'extras'


def _generator():
    spec = importlib.util.spec_from_file_location('update_extras_data',
                                                  ROOT / 'tools' / 'update_extras_data.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_game_facts_the_tools_use_are_up_to_date():
    # In a process of its own: a running game registers the senses a squid
    # grows, and the file is the game as it starts.
    import subprocess
    import sys
    result = subprocess.run([sys.executable, str(ROOT / 'tools' / 'update_extras_data.py'),
                             '--check'], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_those_facts_are_the_games_own():
    from src import inheritance
    from src.brain_constants import newborn_neurons
    data = _generator().game_data()
    assert set(data['newborn_neurons']) == set(newborn_neurons())
    assert data['mutation_rate'] == inheritance.MUTATION_RATE
    assert data['mutation_size'] == inheritance.MUTATION_SIZE
    assert all(src in data['newborn_neurons'] and dst in data['newborn_neurons']
               for src, dst, _weight in data['newborn_connections'])


def test_the_tools_load_nothing_from_the_internet():
    for page in EXTRAS.glob('*.html'):
        text = page.read_text(encoding='utf-8')
        sources = re.findall(r'<script[^>]+src="([^"]+)"', text) \
            + re.findall(r'<link[^>]+href="([^"]+)"', text)
        for source in sources:
            assert not source.startswith(('http:', 'https:', '//')), f'{page.name}: {source}'
            assert (EXTRAS / source).is_file(), f'{page.name}: {source} is missing'
    for licence in ('JSZIP-LICENSE.md', 'CHARTJS-LICENSE.md'):
        assert (EXTRAS / 'vendor' / licence).is_file()


def test_the_breeder_breeds_as_the_game_does():
    """The rule, as the page states and implements it: half of each parent's
    newborn wiring, laid over a newborn brain, the game's mutation - and the
    child written as a brain the game can load."""
    text = (EXTRAS / 'SquidBreeder.html').read_text(encoding='utf-8')
    for needed in ('GAME.newborn_neurons', 'GAME.newborn_connections', 'GAME.mutation_rate',
                   'GAME.mutation_size', 'Math.floor(edges.length/2)', 'brain_state.json',
                   'connections'):
        assert needed in text, needed
    assert 'id="modeGame" checked' in text          # the game's way is the default


def test_the_save_viewer_reads_what_a_save_now_holds():
    text = (EXTRAS / 'SaveViewer.html').read_text(encoding='utf-8')
    for needed in ('lifecycle', 'tint_color', 'fights_won', "startsWith('peer:')",
                   "startsWith('fight:')", 'describeMemory', 'origin_deficit'):
        assert needed in text, needed


def test_a_squids_colour_is_written_to_its_save():
    """Loading read tint_color; saving never wrote it."""
    import inspect
    from src.tamagotchi_logic import TamagotchiLogic
    assert "'tint_color': rgb_of(" in inspect.getsource(TamagotchiLogic.save_game)


def test_meeting_a_squid_for_the_first_time_is_counted_once():
    from plugins.multiplayer.peer_ledger import PeerLedger

    class Statistics:
        other_squids_encountered = 0

        def increment(self, name, amount=1):
            self.other_squids_encountered += amount
            return True

    stats, ledger = Statistics(), PeerLedger(None)
    ledger.last_was_new_squid = True
    assert ledger.count_first_meeting(stats) and stats.other_squids_encountered == 1
    assert not ledger.count_first_meeting(stats) and stats.other_squids_encountered == 1
    from src.squid_statistics import SquidStatistics
    assert 'other_squids_encountered' in SquidStatistics._EVENT_KEYS


# ---------------------------------------------------------------- Laboratory
def _old_save(path):
    """A save as the game wrote it before it kept a timeline."""
    import json
    import zipfile
    from tests.test_life_timeline import _save
    with zipfile.ZipFile(path, 'w') as archive:
        for name, section in _save().items():
            archive.writestr(f'{name}.json', json.dumps(section))
        archive.writestr('uuid.txt', 'SquidSignature    u-1')
    return path


def test_an_older_save_can_be_given_its_timeline(tmp_path):
    import json
    import zipfile
    spec = importlib.util.spec_from_file_location('add_timeline', ROOT / 'tools' / 'add_timeline.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    old = _old_save(tmp_path / 'inky.zip')
    made = tool.add_timeline(old)
    assert made == tmp_path / 'inky.timeline.zip'
    with zipfile.ZipFile(old) as before, zipfile.ZipFile(made) as after:
        assert 'timeline.json' not in before.namelist()            # the original is untouched
        timeline = json.loads(after.read('timeline.json'))
        for name in before.namelist():                             # and nothing else changed
            assert after.read(name) == before.read(name)
    assert timeline['squid']['name'] == 'Inky'
    assert [e['kind'] for e in timeline['events']][0] == 'hatched'
    assert tool.add_timeline(made, made) == made                   # in place, and again, is harmless


def test_every_save_written_carries_the_timeline(tmp_path):
    """The phone writes its saves through write_save_archive, not the
    desktop's save_game: the timeline is added there for whoever lacks it."""
    import json
    import zipfile
    from src.save_archive import write_save_archive
    from tests.test_life_timeline import _save
    write_save_archive(tmp_path / 'phone.zip', _save(), 'u-1')
    with zipfile.ZipFile(tmp_path / 'phone.zip') as archive:
        timeline = json.loads(archive.read('timeline.json'))
    assert timeline['events'] and timeline['neurons']
    # one the game already built is kept as it is
    write_save_archive(tmp_path / 'desktop.zip', dict(_save(), timeline={'events': ['kept']}), 'u-1')
    with zipfile.ZipFile(tmp_path / 'desktop.zip') as archive:
        assert json.loads(archive.read('timeline.json')) == {'events': ['kept']}
    # and the phone build ships the module that writes it
    assert "'life_timeline'" in (ROOT / 'android' / 'prepare_apk.py').read_text(encoding='utf-8')


def test_the_laboratory_shows_the_life_the_game_recorded():
    """It reads timeline.json and works nothing out for itself, so it cannot
    disagree with the game about a squid's life."""
    from src import life_timeline
    page = (EXTRAS / 'Laboratory.html').read_text(encoding='utf-8')
    shared = (EXTRAS / 'vendor' / 'lab.js').read_text(encoding='utf-8')
    for view in ('viewSpecimens', 'viewHistory', 'viewStrata', 'viewWhy', 'viewFamily',
                 'viewCompare', 'viewSession'):
        assert f'function {view}(' in page, view
    assert 'type: \'range\'' in page and 'Lab.drawBrain' in page    # the slider, and the brain then
    assert 'save.timeline' in shared and 'tools/add_timeline.py' in page
    # every stage of life and kind of event the game can write has a colour or a mark
    for era, _title, _about in life_timeline.ERAS:
        assert f'{era}:' in shared, era
    for kind in ('hatched', 'neuron', 'pruned', 'association', 'belief', 'belief_dropped',
                 'encounter', 'mating', 'fight', 'egg', 'death', 'memory'):
        assert re.search(rf'\b{kind}:\s+\{{icon', shared), kind


def test_the_two_laboratories_name_each_other_and_do_different_work():
    """The Neuron Laboratory (in the game, one living neuron, editable) and
    the Laboratory page (saves, whole lives) are not the same thing."""
    page = (EXTRAS / 'Laboratory.html').read_text(encoding='utf-8')
    assert page.count('Neuron Laboratory') >= 2
    assert 'double-click' in page
    game = (ROOT / 'src' / 'laboratory.py').read_text(encoding='utf-8')
    assert 'extras/Laboratory.html' in game and 'lab_whole_life_pointer' in game
    # the page changes nothing and edits no neuron: that is the game's window
    assert 'Unlock editing' not in page and 'Edit Sandbox' not in page


# ------------------------------------------------- breeder's hatchling save
def test_the_breeder_writes_a_hatchling_the_game_opens():
    """A newborn with the child's brain: no drives (the game gives it a
    hatchling's), its parents and each inherited synapse on record, and marked
    as bred in the laboratory. Only for a child bred as the game breeds."""
    text = (EXTRAS / 'SquidBreeder.html').read_text(encoding='utf-8')
    for needed in ('function hatchlingSave(', 'bred_by:"laboratory"', '"game_state.json"',
                   '"brain_state.json"', 'SquidSignature    ', 'made.uuid.replace(/-/g,"_")+".zip"',
                   'inheritance', 'GAME.personalities'):
        assert needed in text, needed
    # its drives are never invented by the page: the squid is written without any
    assert 'squid:{name,personality,uuid,is_sick:false,lineage,inherited_from:lineage.parents},' in text
    assert 'asGame ? "block" : "none"' in text
    from src.personality import Personality
    assert _generator().game_data()['personalities'] == [p.value for p in Personality]


def test_an_heir_is_still_an_heir_after_loading():
    """inherited_from exists only on a squid that hatched from a parent's egg,
    so the load loop (which sets what the squid already has) dropped it."""
    import inspect
    from src.tamagotchi_logic import TamagotchiLogic
    source = inspect.getsource(TamagotchiLogic.load_game)
    assert 'self.squid.inherited_from = [' in source and "squid_data.get('lineage')" in source


def test_there_is_one_trainer():
    """The browser step trainer reimplemented the brain and fell behind it;
    the headless trainer, served live, took its place."""
    assert not (EXTRAS / 'StepTrainer.html').exists()
    assert not (ROOT / 'headless' / 'headless_launcher.html').exists()
    page = (ROOT / 'headless' / 'trainer.html').read_text(encoding='utf-8')
    assert not re.findall(r'<script[^>]+src=', page) and 'https://' not in page
