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
    saved = (D._scale_factor, D._ratio, D._small_screen, D._window_base)
    try:
        D.initialize(1512, 982, 2.0)
        assert not D._small_screen                       # 3024x1964 real pixels
        assert abs(D.get_scale_factor() - (1964 / 1920) / 2) < 1e-6
        assert (D.scale(1344), D.scale(936)) == (687, 478)   # the window, in points
        assert D.window_size() == (687, 478)
        # Half size in points - and the 2% by which this screen is larger
        # than the one the game was designed on.
        assert abs(D.squid_scale() - 0.5 * 1964 / 1920) < 1e-6 and D.points(64) == 33
        pixmap = QtGui.QPixmap(64, 48)
        assert (D.to_points(pixmap).width(), D.to_points(pixmap).height()) == (33, 25)
        # On the screen it was designed for, nothing is scaled at all.
        D.initialize(2880, 1920, 1.0)
        assert D.window_size() == (1344, 936) and D.tank_scale() == 1.0
        assert D.to_points(pixmap) is pixmap and D.points(64) == 64
    finally:
        D._scale_factor, D._ratio, D._small_screen, D._window_base = saved


def test_a_squid_takes_the_same_share_of_its_tank_on_every_screen():
    """The tank is one picture, drawn larger or smaller: the squid, the food
    and the rocks are scaled with the window. (On a 1080p screen the window
    was drawn at 48% of its design, the squid at 70% and food at full size -
    a squid half as tall as its tank.)"""
    from src.display_scaling import DisplayScaling as D
    saved = (D._scale_factor, D._ratio, D._small_screen, D._window_base)
    try:
        shares = []
        for width, height, ratio in ((2880, 1920, 1.0), (1920, 1080, 1.0), (2560, 1440, 1.0),
                                     (3840, 2160, 1.0), (1366, 768, 1.0), (1512, 982, 2.0),
                                     (1280, 720, 1.5)):
            D.initialize(width, height, ratio)
            window_width, _window_height = D.window_size()
            squid = 253 * D.squid_scale()                # left1.png is 253 wide
            food = D.points(64)
            shares.append((squid / window_width, food / window_width))
        design = shares[0]
        assert abs(design[0] - 253 / 1344) < 1e-9
        for squid_share, food_share in shares[1:]:
            assert abs(squid_share - design[0]) < 0.002
            assert abs(food_share - design[1]) < 0.003
        D.initialize(1920, 1080, 1.0)
        assert D.window_size() == (688, 458)                 # as it always was
        assert abs(D.squid_scale() - 688.5 / 1344) < 1e-3    # not 0.7
    finally:
        D._scale_factor, D._ratio, D._small_screen, D._window_base = saved


def test_feed_clean_and_medicine_share_the_whole_width_of_the_window():
    from src.ui import Ui

    class Tank:
        TANK_TOP = Ui.TANK_TOP
        window_width = 688
        _button_height, _button_spacing = 28, 9
        action_buttons = []

    tank = Tank()

    class Proxy:
        def setPos(self, x, y):
            self.x, self.y = x, y
    tank.action_buttons = [(QtWidgets.QPushButton(name), Proxy())
                           for name in ('FEED', 'CLEAN', 'MEDICINE')]
    Ui.layout_action_buttons(tank)
    widths = {button.width() for button, _ in tank.action_buttons}
    assert widths == {217} and all(b.height() == 28 for b, _ in tank.action_buttons)
    left = tank.action_buttons[0][1].x
    right = tank.action_buttons[-1][1].x + 217
    assert left == 9 and 688 - right in (9, 10)             # edge to edge, one gap each end
    assert all(0 < proxy.y and proxy.y + 28 <= Ui.TANK_TOP for _, proxy in tank.action_buttons)
    # ... and again when the window is made wider.
    tank.window_width = 1000
    Ui.layout_action_buttons(tank)
    assert {button.width() for button, _ in tank.action_buttons} == {321}


def test_each_button_rests_in_its_own_pastel():
    """Feed pastel green, Clean pastel blue, Medicine pastel red - at rest,
    not only under the pointer."""
    import inspect
    from src import ui
    from src.ui import ActionButton
    text = inspect.getsource(ui)
    for label, pastel in (('feed_btn', '#C8E6C9'), ('clean_btn', '#B3E5FC'),
                          ('medicine_btn', '#FFCDD2')):
        assert f'(loc.get("{label}"), "{pastel}"' in text
    button = ActionButton('FEED', '#A5D6A7', '#4CAF50', 12, base_color='#C8E6C9')
    assert 'background-color: #C8E6C9' in button.styleSheet()
    button.is_hovered = True
    button.update_style()
    assert 'background-color: #A5D6A7' in button.styleSheet()
    button.is_pressed = True
    button.update_style()
    assert 'background-color: #4CAF50' in button.styleSheet()
