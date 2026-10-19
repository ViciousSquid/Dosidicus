"""Authoritative fight outcomes, duplicate reports, persistent UI counters."""
from types import SimpleNamespace
import sys
from pathlib import Path

import pytest
from PyQt5 import QtWidgets

from src.squid_statistics import SquidStatistics
from src.brain_statistics_tab import StatisticsTab
from src.save_manager import SaveManager
from plugins.multiplayer.host_body import HostBody
from plugins.multiplayer.identity import SquidIdentity
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
from plugins.multiplayer.visitor_mind import VisitorMind


def squid(name):
    pet = SimpleNamespace(name=name, is_sick=False)
    pet.statistics = SquidStatistics(pet)
    return pet


@pytest.mark.parametrize('roll', [.1, .9])
def test_host_resolves_once_and_guest_counts_duplicate_messages_once(roll, monkeypatch):
    monkeypatch.setattr('plugins.multiplayer.mp_plugin_logic.random.random', lambda: roll)
    host, guest = squid('Host'), squid('Guest')
    logic = SimpleNamespace(squid=host)
    plugin = MultiplayerPlugin()
    plugin.tamagotchi_logic = logic
    plugin.host_body = HostBody(tamagotchi_logic=logic)
    actor = plugin.host_body.admit(
        SquidIdentity('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Guest'), 'visit1', 400, 300)
    visitor = VisitorMind(SimpleNamespace(squid=guest))
    visitor.visit_id = 'visit1'
    assert plugin.resolve_fight(actor, 'fight1')
    assert not plugin.resolve_fight(actor, 'fight1')
    reports = plugin.host_body.drain_consequences(actor)
    assert len(reports) == 3
    for report in reports + reports:
        visitor.on_consequence(report.to_payload())
    assert host.statistics.fights_won == guest.statistics.fights_lost
    assert host.statistics.fights_lost == guest.statistics.fights_won
    assert host.statistics.fights_won + host.statistics.fights_lost == 1
    assert guest.statistics.fights_won + guest.statistics.fights_lost == 1


def test_statistics_tab_and_save_archive_retain_win_loss_totals(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    pet = squid('Pet')
    pet.statistics.record_fight_result('a', True)
    pet.statistics.record_fight_result('b', True)
    pet.statistics.record_fight_result('c', False)
    manager = SaveManager(str(tmp_path))
    path = manager.save_game({'game_state': {'squid': {'uuid': 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'}},
                              'statistics': pet.statistics.to_dict()})
    pet.statistics.load_statistics(manager._load_single_save(path)['statistics'])
    tab = StatisticsTab(tamagotchi_logic=SimpleNamespace(squid=pet))
    try:
        tab._sync_from_squid_statistics()
        tab.update_display()
        assert tab.stat_labels['fights_won'].text() == '2'
        assert tab.stat_labels['fights_lost'].text() == '1'
    finally:
        tab.update_timer.stop()
        tab.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('local,peer,by,allowed', [
    ('timid','adventurous','resident',False),
    ('adventurous','timid','visitor',False),
    ('timid','adventurous','visitor',True),
    ('adventurous','timid','resident',True),
    ('timid','timid','visitor',False),
])
def test_mobile_timid_never_starts_but_can_be_attacked(local, peer, by, allowed):
    sys.path.append(str(Path(__file__).resolve().parents[1]/'android'))
    from dosidicus_mobile.engine import Simulation, Personality
    sim = Simulation()
    sim.squid.personality = Personality.from_value(local)
    guest = sim.add_visitor({}, name='Guest')
    guest['personality'] = peer
    sim._start_fight(guest, instigator=by)
    assert (sim.fight is not None) == allowed
