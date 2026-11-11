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
