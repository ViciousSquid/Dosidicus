"""The fight ladder (Fisticuffs! -> Scuffle -> Tussle -> Slugfest), CIRCLE OF
LIFE, and the multiplayer risk notice.

Fights reach the achievements through the real seams: the host resolving a
fight, the visitor hearing about it (three times, as the host repeats it), and
the core plugin manager's on_fight hook in between - so a fight counts once
for each squid however it is reported. CIRCLE OF LIFE is the core's
on_squid_died, which only a parent that starved after mating can trigger.
"""
import logging
from types import SimpleNamespace
from unittest import mock

import pytest
from PyQt5 import QtWidgets

from src.lifecycle import Lifecycle
from src.plugin_manager import PluginManager
from src.squid_statistics import SquidStatistics
from plugins.achievements.main import AchievementsPlugin
from plugins.multiplayer.host_body import HostBody
from plugins.multiplayer.identity import SquidIdentity
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
from plugins.multiplayer.remote_protocol import CONSEQUENCE_FIGHT, Consequence
from plugins.multiplayer.visitor_mind import VisitorMind

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

GUEST_UUID = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
LADDER = ('first_fight', 'fights_5', 'fights_20', 'fights_50')


def squid(name):
    pet = SimpleNamespace(name=name, is_sick=False)
    pet.statistics = SquidStatistics(pet)
    return pet


@pytest.fixture
def achievements(tmp_path, monkeypatch):
    """An achievements plugin listening on the real (singleton) plugin manager."""
    monkeypatch.chdir(tmp_path)          # unlocks are logged under ./saves
    manager = PluginManager()
    plugin = AchievementsPlugin()
    plugin.plugin_manager = manager
    plugin.logger = logging.getLogger('test-achievements')
    plugin._setup_timers()
    plugin._subscribe_to_hooks()
    was_enabled = 'achievements' in manager.enabled_plugins
    manager.enabled_plugins.add('achievements')
    yield plugin
    plugin.notification_timer.stop()
    if plugin.current_notification is not None:
        plugin.current_notification.close()
    for hook, subscribers in manager.hooks.items():
        manager.hooks[hook] = [s for s in subscribers
                               if getattr(s['callback'], '__self__', None) is not plugin]
    if not was_enabled:
        manager.enabled_plugins.discard('achievements')


def unlocked(plugin, ids=LADDER):
    return [aid for aid in ids if aid in plugin.unlocked]


def test_the_ladder_unlocks_at_one_five_twenty_and_fifty_fights(achievements):
    expected = {1: ['first_fight'], 4: ['first_fight'],
                5: ['first_fight', 'fights_5'], 19: ['first_fight', 'fights_5'],
                20: ['first_fight', 'fights_5', 'fights_20'],
                49: ['first_fight', 'fights_5', 'fights_20'],
                50: list(LADDER)}
    for count in range(1, 51):
        achievements.on_squid_fought()
        if count in expected:
            assert unlocked(achievements) == expected[count], count
    assert achievements.progress['fights_50'] == 50


def test_the_host_counts_a_fight_once(achievements, monkeypatch):
    monkeypatch.setattr('plugins.multiplayer.mp_plugin_logic.random.random', lambda: .1)
    host = squid('Host')
    plugin = MultiplayerPlugin()
    plugin.plugin_manager = PluginManager()
    plugin.tamagotchi_logic = SimpleNamespace(squid=host)
    plugin.host_body = HostBody(tamagotchi_logic=plugin.tamagotchi_logic)
    actor = plugin.host_body.admit(SquidIdentity(GUEST_UUID, 'Guest'), 'visit1', 400, 300)

    assert plugin.resolve_fight(actor, 'fight1')
    assert not plugin.resolve_fight(actor, 'fight1')

    assert achievements.statistics['fights'] == 1
    assert unlocked(achievements) == ['first_fight']


def test_the_visitor_counts_a_repeated_report_once(achievements):
    guest = squid('Guest')
    plugin = MultiplayerPlugin()
    plugin.plugin_manager = PluginManager()
    plugin.tamagotchi_logic = SimpleNamespace(squid=guest)
    visitor = VisitorMind(plugin.tamagotchi_logic)
    visitor.on_fight = plugin.announce_fight
    visitor.visit_id = 'visit1'
    report = Consequence('visit1', CONSEQUENCE_FIGHT, 0.0,
                         {'fight_id': 'fight1', 'won': False})

    for _ in range(6):                     # three per round, two rounds
        visitor.on_consequence(report.to_payload())

    assert guest.statistics.fights_lost == 1
    assert achievements.statistics['fights'] == 1
    assert unlocked(achievements) == ['first_fight']


def test_circle_of_life_is_a_parent_dying_for_its_egg(achievements):
    manager = PluginManager()
    living = SimpleNamespace(lifecycle=Lifecycle())
    manager.trigger_hook('on_squid_died', squid=living)
    assert 'circle_of_life' not in achievements.unlocked

    parent = SimpleNamespace(lifecycle=Lifecycle(), hunger=100.0, health=0.1)
    assert parent.lifecycle.record_reproduction('visit1-mate', GUEST_UUID, 'Mate')
    assert parent.lifecycle.starve(parent, 1.0, 90.0)
    manager.trigger_hook('on_squid_died', squid=parent)
    assert 'circle_of_life' in achievements.unlocked


def test_a_parent_refusing_food_is_not_counted_as_fed(achievements):
    meals = []
    pet = SimpleNamespace(eat=lambda food: meals.pop(0))
    achievements.squid = pet
    achievements._install_hooks()
    try:
        meals.extend([False, False, True])
        pet.eat('sushi')
        pet.eat('sushi')
        assert achievements.statistics.get('times_fed', 0) == 0
        pet.eat('sushi')
        assert achievements.statistics['times_fed'] == 1
    finally:
        achievements._uninstall_hooks()


NOTICE = ("Enabling multiplayer introduces new experiences that may permanently "
          "alter your squid's behaviour, neural development and life.\n\n"
          "Encounters may result in fights, reproduction or even death.\n\n"
          "Changes to your squid and its saved state cannot be undone.")


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    from src import config_manager
    path = tmp_path / 'config.ini'
    real = config_manager.ConfigManager
    monkeypatch.setattr(config_manager, 'ConfigManager',
                        lambda *args, **kwargs: real(str(path)))
    return path


def test_the_question_is_asked_until_accepted_and_then_never_again(config_path):
    from src.config_manager import ConfigManager
    plugin = MultiplayerPlugin()
    no, yes = QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes
    with mock.patch.object(QtWidgets.QMessageBox, 'question', side_effect=[no, yes]) as asked:
        assert not plugin.confirm_risk_once()            # declined: stays off
        assert not ConfigManager().get_multiplayer_risk_notice_shown()
        assert plugin.confirm_risk_once()                # asked again; accepted
        assert plugin.confirm_risk_once()                # never asked a third time
    assert asked.call_count == 2
    title, text = asked.call_args.args[1:3]
    assert title == "Enable peer-to-peer evolution?"
    assert text == "Enable peer-to-peer evolution?\n\n" + NOTICE
    assert asked.call_args.args[4] == no                 # No is the default
    assert ConfigManager().get_multiplayer_risk_notice_shown()


def test_declining_leaves_multiplayer_off(config_path):
    plugin = MultiplayerPlugin()
    plugin.logger = logging.getLogger('test-multiplayer')
    plugin.is_setup = True
    plugin.network_node = None
    with mock.patch.object(QtWidgets.QMessageBox, 'question',
                           return_value=QtWidgets.QMessageBox.No):
        assert plugin.enable() is False


def test_enabling_multiplayer_asks_first():
    plugin = MultiplayerPlugin()
    plugin.logger = logging.getLogger('test-multiplayer')
    plugin.is_setup = True
    plugin.network_node = None          # stops enable() before any networking
    with mock.patch.object(plugin, 'confirm_risk_once', return_value=True) as asked:
        plugin.enable()
    asked.assert_called_once_with()
