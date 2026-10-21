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


def test_a_retina_mac_is_sized_in_real_pixels_and_drawn_in_points():
    """A 14in MacBook Pro reports 1512x982 points at 2x. Taken as pixels it was
    a small 1080p screen: the window shrank while sprites kept their pixel
    size in points, twice their size on screen."""
    from src.display_scaling import DisplayScaling as D
    saved = (D._scale_factor, D._ratio, D._small_screen)
    try:
        D.initialize(1512, 982, 2.0)
        assert not D._small_screen                       # 3024x1964 real pixels
        assert abs(D.get_scale_factor() - (1964 / 1920) / 2) < 1e-6
        assert (D.scale(1344), D.scale(936)) == (687, 478)   # the window, in points
        assert D.squid_scale() == 0.5 and D.points(64) == 32
        pixmap = QtGui.QPixmap(64, 48)
        assert (D.to_points(pixmap).width(), D.to_points(pixmap).height()) == (32, 24)
        # Where Qt draws in pixels nothing changes.
        D.initialize(1920, 1080, 1.0)
        assert D._small_screen and D.squid_scale() == 0.7 and D.points(64) == 64
        assert D.to_points(pixmap) is pixmap
        before = min(1920 / 2880, 1080 / 1920) * 0.85          # the factor as it always was
        assert (D.scale(1440), D.scale(960)) == (int(1440 * before), int(960 * before))
    finally:
        D._scale_factor, D._ratio, D._small_screen = saved
