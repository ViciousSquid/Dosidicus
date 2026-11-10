"""Every change to the score floats up out of the squid.

Points gained rise in green ("+75"), points lost in red ("-50"). Everything
that awards or takes points - eating, neurogenesis, being startled, clearing
poop, hatching - goes through StatisticsWindow.award, so that is where it is
shown, once, for all of them.
"""
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PyQt5 import QtGui, QtWidgets                                  # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from src.statistics_window import StatisticsWindow                  # noqa: E402


def game():
    scene = QtWidgets.QGraphicsScene()
    body = scene.addPixmap(QtGui.QPixmap(130, 75))
    floated = []
    ui = SimpleNamespace(show_floating_score=lambda item, text, colour=None:
                         floated.append((item, text, colour.name() if colour else None)))
    squid = SimpleNamespace(ui=ui, squid_item=body, tamagotchi_logic=None, status='roaming',
                            hunger=10, happiness=50, cleanliness=50, sleepiness=10,
                            health=100, satisfaction=50, curiosity=50, anxiety=20,
                            is_sleeping=False)
    window = StatisticsWindow(squid)
    window.roll_timer.stop()
    return window, scene, body, floated


def test_points_gained_float_up_from_the_squid_in_green():
    window, _scene, body, floated = game()
    window.award(75)                                     # it ate
    assert floated == [(body, '+75', '#32cd32')]
    window.add_score_for_neuron_creation()               # it grew a neuron
    assert floated[-1] == (body, '+500', '#32cd32')
    assert window.score == 575


def test_points_lost_float_up_from_the_squid_in_red():
    window, _scene, body, floated = game()
    window.award(1000)
    window.deduct_score_for_startle()
    assert floated[-1] == (body, '-50', '#dc2828')
    window.award(-250)
    assert floated[-1] == (body, '-250', '#dc2828')
    assert window.score == 700


def test_the_number_is_what_the_score_actually_changed_by():
    window, _scene, body, floated = game()
    window.award(100)                                    # food...
    window.award(100)                                    # ...and again at once: a combo
    assert [text for _, text, _ in floated] == ['+100', '+200']
    del floated[:]
    window.set_score(20)
    window.award(-50)                                    # it cannot go below nothing
    assert floated == [(body, '-20', '#dc2828')]
    window.award(-50)                                    # nothing left to lose: nothing shown
    assert len(floated) == 1
    window.set_score(9990)
    window.award(75)
    assert floated[-1][1] == '+9'                        # nor above the top


def test_points_for_something_else_rise_from_that_thing():
    window, scene, body, floated = game()
    poop = scene.addPixmap(QtGui.QPixmap(20, 20))
    window.award(5, at=poop)                             # a poop cleared away
    assert floated == [(poop, '+5', '#32cd32')]
    text = (ROOT / 'src' / 'ui.py').read_text(encoding='utf-8')
    assert 'statistics_window.award(5, at=item)' in text
    assert 'self.show_floating_score(item, "+5")' not in text      # shown once, not twice


def test_nothing_floats_from_a_squid_that_is_not_in_the_tank():
    window, _scene, body, floated = game()
    body.setVisible(False)                               # out visiting
    window.award(75)
    assert floated == [] and window.score == 75          # the points still count
    window.squid = SimpleNamespace()                     # or no tank at all (headless)
    window.award(75)
    assert window.score == 150


def test_everything_that_changes_the_score_goes_through_award():
    """Nothing adds to or takes from the score behind its back - or its
    points would not be shown."""
    changed_directly = re.compile(r'\.score\s*(\+=|-=)')
    offenders = []
    for folder in ('src', 'plugins'):
        for path in (ROOT / folder).rglob('*.py'):
            if path.name == 'statistics_window.py':
                continue
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if changed_directly.search(line) and 'statistics_window' in line:
                    offenders.append(f'{path.relative_to(ROOT)}:{number}')
    assert not offenders, offenders
