"""The Brain Network tab's "Hebbian Cycle" shows how many cycles have run.

It used to show the seconds to the next one, which the Learning tab also
shows. The count is the plasticity engine's committed cycles, saved with the
brain, so it carries on across sessions.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5 import QtWidgets                                         # noqa: E402

from src.plasticity import PlasticityEngine                        # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_every_committed_cycle_is_counted_and_the_count_is_saved():
    engine = PlasticityEngine()
    weights = {('hunger', 'act_eat'): 0.1}
    for _ in range(3):
        engine.commit(weights=weights, neuron_names=['hunger', 'act_eat'])
    assert engine.commit_count == 3
    reloaded = PlasticityEngine()
    reloaded.from_dict(engine.to_dict())
    assert reloaded.commit_count == 3


def test_the_network_tab_shows_the_count_not_a_countdown():
    from src.brain_network_tab import NetworkTab
    tab = SimpleNamespace(
        hebbian_timer_label=QtWidgets.QLabel(),
        brain_widget=SimpleNamespace(plasticity=SimpleNamespace(commit_count=12),
                                     hebbian_countdown_seconds=27),
        tamagotchi_logic=SimpleNamespace(simulation_speed=0))      # paused: still the count
    NetworkTab.update_hebbian_label(tab)
    assert tab.hebbian_timer_label.text().endswith(': 12')
