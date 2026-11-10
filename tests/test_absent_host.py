"""A squid that is out visiting has no encounters in its own tank.

Four tanks linked over the internet showed it: Bolt swam out to Inky's tank,
Pesto swam into Bolt's - empty - tank, and three minutes later Bolt
"remembered a good encounter with Pesto", a squid it had never been in the
same water as. A squid's experiences are of where it is.
"""
import logging
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5 import QtWidgets                                         # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from plugins.multiplayer.identity import SquidIdentity             # noqa: E402
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin  # noqa: E402

PESTO = SquidIdentity(uuid='3f2b8c1e-5d47-4a9b-8e21-7c6d5b4a3f20', name='Pesto')


class View:
    """The tank's record of which other squid are in it."""

    def __init__(self):
        self.presences = {}

    def prune(self, now):
        pass

    def drain_contests(self):
        return []

    def put(self, identity):
        self.presences[identity.uuid] = SimpleNamespace(
            uuid=identity.uuid, identity=identity, last_update=time.time(),
            distance=120.0, status='exploring', x=300.0, y=300.0)


class Ledger:
    def __init__(self):
        self.records = []

    def summary(self, uuid):
        return SimpleNamespace(encounters=0)

    def record(self, record):
        self.records.append(record)


def host(away):
    plugin = MultiplayerPlugin()
    plugin.logger = logging.getLogger('absent-host')
    squid = SimpleNamespace(hunger=30., happiness=70., anxiety=20., curiosity=60.,
                            sleepiness=10., satisfaction=50., cleanliness=90.,
                            status='exploring', uuid='11111111-2222-4333-8444-555555555555')
    plugin.tamagotchi_logic = SimpleNamespace(squid=squid)
    plugin.peer_ledger = Ledger()
    plugin.conspecific_view = View()
    plugin.visitor_mind = SimpleNamespace(perception=SimpleNamespace(away=away))
    plugin.seen = []
    plugin._perceive_visitors = lambda squid, present: plugin.seen.append(sorted(present))
    filed = []
    close = plugin.close_encounter

    def closing(peer_uuid, drives=None, now=None):
        filed.append(peer_uuid)
        plugin.open_encounters.pop(peer_uuid, None)
    plugin.close_encounter = closing
    plugin.filed = filed
    plugin._really_close = close
    return plugin


def test_a_squid_at_home_meets_whoever_comes_into_its_tank():
    plugin = host(away=False)
    plugin.conspecific_view.put(PESTO)
    plugin.update_encounters()
    assert list(plugin.open_encounters) == [PESTO.uuid]
    assert plugin.seen[-1] == [PESTO.uuid]


def test_a_squid_that_is_out_does_not_meet_a_visitor_to_its_empty_tank():
    plugin = host(away=True)
    plugin.conspecific_view.put(PESTO)             # Pesto swims into the empty tank
    for _ in range(5):
        plugin.update_encounters()
    assert plugin.open_encounters == {}            # no encounter: it is not there
    assert plugin.seen[-1] == []                   # and its senses report nobody
    assert plugin.filed == [] and plugin.peer_ledger.records == []


def test_an_encounter_ends_when_the_squid_swims_out():
    plugin = host(away=False)
    plugin.conspecific_view.put(PESTO)
    plugin.update_encounters()
    assert PESTO.uuid in plugin.open_encounters    # they are together...
    plugin.visitor_mind.perception.away = True     # ...until it leaves for another tank
    plugin.update_encounters()
    assert plugin.open_encounters == {}
    assert plugin.filed == [PESTO.uuid]            # what they had is filed, then and there
    plugin.conspecific_view.put(PESTO)             # Pesto stays on in the empty tank
    plugin.update_encounters()
    assert plugin.open_encounters == {} and plugin.filed == [PESTO.uuid]
    plugin.visitor_mind.perception.away = False    # home again, and Pesto is still here:
    plugin.conspecific_view.put(PESTO)
    plugin.update_encounters()
    assert PESTO.uuid in plugin.open_encounters    # a new encounter, from now
