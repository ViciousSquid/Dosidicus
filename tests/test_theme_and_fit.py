"""The game reads in a dark system theme, and the brain fits its window.

In macOS dark mode the windows turned dark and their text white, while the
game's own light colours stayed: memory cards, the Laboratory and the
Statistics tab came out white on pastel or white on white. In a dark theme the
game now draws itself light (src/theme.py); a memory card's text follows the
card's colour whatever the theme. The brain widget forced itself to at least
1280x900 whatever room the Brain Tool gave it, so in the 800x900 window the
Brain Tool opens at the network was drawn too big and cut off.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5 import QtGui, QtWidgets                                  # noqa: E402

from src import theme                                               # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def dark_palette():
    palette = QtGui.QPalette()
    for role, colour in ((QtGui.QPalette.Window, '#2b2b2b'), (QtGui.QPalette.WindowText, '#ffffff'),
                         (QtGui.QPalette.Base, '#1f1f1f'), (QtGui.QPalette.Text, '#ffffff')):
        palette.setColor(role, QtGui.QColor(colour))
    return palette


def test_a_dark_system_theme_is_drawn_light_and_a_light_one_is_left_alone():
    style, palette = _APP.style().objectName(), _APP.palette()
    try:
        _APP.setPalette(dark_palette())
        assert theme.is_dark(_APP.palette())
        assert theme.keep_light(_APP)
        assert _APP.style().objectName().lower() == 'fusion'
        assert not theme.is_dark(_APP.palette())
        text = _APP.palette().color(QtGui.QPalette.WindowText)
        assert text.lightness() < 100                          # dark text, readable
        assert not theme.keep_light(_APP)                      # light: nothing to do
    finally:
        _APP.setStyle(style)
        _APP.setPalette(palette)


def test_a_memory_cards_text_follows_the_card_not_the_theme():
    from src.brain_memory_tab import _text_colour_on
    for pastel in ('#D1FFD1', '#FFD1DC', '#FFFACD', '#E8F4FD', '#B8D4F0'):
        assert _text_colour_on(pastel) == '#1d1d1f'
    assert _text_colour_on('#4169E1') == '#ffffff'             # neurogenesis, dark blue


def test_the_brain_is_drawn_in_whatever_room_it_is_given():
    from src.brain_widget import BrainWidget
    from src.config_manager import ConfigManager
    brain = BrainWidget(config=ConfigManager())
    brain._cleanup_render_worker()
    for name in ('neurogenesis_timer', 'animation_timer', '_render_timer',
                 '_brain_export_timer', '_link_fade_timer'):
        timer = getattr(brain, name, None)
        if timer is not None:
            timer.stop()
    brain.show()                         # a hidden widget is sent no resize event
    brain.resize(740, 560)
    _APP.processEvents()
    try:
        assert (brain.width(), brain.height()) == (740, 560)
    finally:
        brain.hide()
