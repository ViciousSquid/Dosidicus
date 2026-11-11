"""Small things in the tank and the Brain Tool that a player looks straight at.

- Every icon above the squid's head (neurogenesis, startled, sick, curious)
  sits just above it, at any tank size, and is hidden while the squid is out.
- A visiting squid's floating name can be read against a white tank.
- Load Brain is a floppy-disk icon, and it, Reset and the Brain Designer
  button are one group of three buttons the same size.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PyQt5 import QtGui, QtWidgets                                  # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from src.display_scaling import DisplayScaling as D                 # noqa: E402
from src.squid import Squid                                         # noqa: E402


def _squid(scene):
    """Just enough of a squid to stand under an icon."""
    body = scene.addPixmap(QtGui.QPixmap(130, 75))
    squid = SimpleNamespace(squid_x=300, squid_y=200, squid_width=130, squid_height=75,
                            squid_item=body, HEAD_ICON_GAP=Squid.HEAD_ICON_GAP,
                            ng_icon=None, startled_icon=None, sick_icon_item=None,
                            mental_state_manager=None)
    for name in ('_head_icons', 'place_head_icon', 'set_in_tank', 'update_head_icon_positions',
                 'update_neurogenesis_icon_position', 'update_startled_icon_position',
                 'update_sick_icon_position'):
        setattr(squid, name, getattr(Squid, name).__get__(squid))
    return squid


def _with_screen(width, height):
    saved = (D._scale_factor, D._ratio, D._small_screen, D._window_base)
    D.initialize(width, height, 1.0)
    return saved


def _restore(saved):
    D._scale_factor, D._ratio, D._small_screen, D._window_base = saved


def test_the_head_icon_sits_just_above_the_squid_at_any_tank_size():
    for screen in ((2880, 1920), (2560, 1440), (1920, 1080)):
        saved = _with_screen(*screen)
        try:
            scene = QtWidgets.QGraphicsScene()
            squid = _squid(scene)
            icon_image = D.to_points(QtGui.QPixmap(72, 90))          # ng.png, sick.png, curious.png
            for name in ('ng_icon', 'startled_icon', 'sick_icon_item'):
                squid.ng_icon = squid.startled_icon = squid.sick_icon_item = None
                icon = scene.addPixmap(icon_image)
                setattr(squid, name, icon)
                squid.update_head_icon_positions()
                gap = squid.squid_y - (icon.y() + icon.pixmap().height())
                # A small gap, the same share of the tank on every screen -
                # not the 54 pixels it floated at on a 1080p screen.
                assert gap == D.points(10) and 0 < gap <= 10, (screen, name, gap)
                centre = icon.x() + icon.pixmap().width() / 2
                assert abs(centre - (squid.squid_x + squid.squid_width / 2)) <= 1
                assert icon.isVisible()
        finally:
            _restore(saved)


def test_only_one_icon_is_shown_above_the_head_at_a_time():
    """A squid can be curious and have just grown a neuron at once. One icon
    is shown: neurogenesis whenever it is there - it lasts only a few seconds
    - otherwise the first that applies of sick, startled, then the other
    states. The rest wait."""
    from src.mental_states import MentalStateManager
    scene = QtWidgets.QGraphicsScene()
    squid = _squid(scene)
    manager = MentalStateManager(squid, scene)
    squid.mental_state_manager = manager
    manager.set_state('curious', True)
    curious = manager.mental_states['curious'].icon_item
    squid.update_head_icon_positions()
    assert curious.isVisible()                               # alone: shown

    ng = scene.addPixmap(curious.pixmap())                   # ...then it grows a neuron
    squid.ng_icon = ng
    squid.update_head_icon_positions()
    assert ng.isVisible() and not curious.isVisible()        # one icon, not two
    centre = ng.x() + ng.pixmap().width() / 2
    assert abs(centre - (squid.squid_x + squid.squid_width / 2)) <= 1

    startled = scene.addPixmap(curious.pixmap())             # ...and something startles it
    squid.startled_icon = startled
    squid.update_head_icon_positions()
    assert [i.isVisible() for i in (ng, startled, curious)] == [True, False, False]

    sick = scene.addPixmap(curious.pixmap())                 # ...and it is sick as well:
    squid.sick_icon_item = sick
    squid.update_head_icon_positions()                       # neurogenesis is still the one
    assert [i.isVisible() for i in (ng, sick, startled, curious)] == [True, False, False, False]

    # The few seconds pass. The next takes its place, in the same spot: sick,
    scene.removeItem(ng); squid.ng_icon = None
    squid.update_head_icon_positions()
    assert [i.isVisible() for i in (sick, startled, curious)] == [True, False, False]
    scene.removeItem(sick); squid.sick_icon_item = None      # then startled,
    squid.update_head_icon_positions()
    assert [i.isVisible() for i in (startled, curious)] == [True, False]
    scene.removeItem(startled); squid.startled_icon = None   # then the rest.
    squid.squid_x += 90                                      # And it moves with the squid.
    squid.update_head_icon_positions()
    assert curious.isVisible()
    centre = curious.x() + curious.pixmap().width() / 2
    assert abs(centre - (squid.squid_x + squid.squid_width / 2)) <= 1
    assert sum(1 for i in squid._head_icons() if i.isVisible()) == 1


def test_a_squid_that_swims_out_takes_its_head_icon_with_it():
    from src.mental_states import MentalStateManager
    scene = QtWidgets.QGraphicsScene()
    squid = _squid(scene)
    manager = MentalStateManager(squid, scene)
    squid.mental_state_manager = manager
    manager.set_state('curious', True)
    squid.ng_icon = scene.addPixmap(QtGui.QPixmap(72, 90))
    squid.update_head_icon_positions()
    curious = manager.mental_states['curious'].icon_item
    assert squid.ng_icon.isVisible() and not curious.isVisible()
    squid.set_in_tank(False)                     # it has left for another tank
    assert not squid.squid_item.isVisible()
    assert not squid.ng_icon.isVisible() and not curious.isVisible()
    squid.set_in_tank(True)                      # and come home
    assert squid.ng_icon.isVisible() and not curious.isVisible()
    # Both ways out of the tank, and both ways back, go through it.
    for name in ('src/squid.py', 'plugins/multiplayer/visitor_mind.py',
                 'plugins/multiplayer/mp_plugin_logic.py'):
        assert 'set_in_tank(' in (ROOT / name).read_text(encoding='utf-8'), name


def test_a_visitors_name_can_be_read_on_a_white_tank():
    from plugins.multiplayer.remote_entity_manager import RemoteEntityManager
    entities = RemoteEntityManager(QtWidgets.QGraphicsScene(), 1280, 900)
    entities.position_update_timer.stop()
    entities.swim_timer.stop()
    entities.update_remote_squid('squid_vis001', {
        'x': 0., 'y': 300., 'image_direction_key': 'left',
        'identity': {'uuid': '3f2b8c1e-5d47-4a9b-8e21-7c6d5b4a3f20', 'name': 'Pesto'}},
        is_new_arrival=True)
    info = entities.remote_squids['squid_vis001']
    name = info['id_text']
    assert name.toPlainText() == 'Pesto'
    colour = name.defaultTextColor()
    assert colour.lightness() < 60 and colour.alpha() == 255        # was light grey, and see-through
    assert name.font().bold() and name.font().pointSize() >= 10
    assert info['status_text'].defaultTextColor().lightness() < 130  # was yellow on white
    for colour in (entities.NAME_COLOUR, entities.STATUS_COLOUR, entities.ARRIVING_COLOUR):
        assert colour.lightness() < 130


def test_load_brain_is_a_floppy_disk_in_a_group_of_three_buttons():
    from src.custom_brain_loader import add_load_brain_button
    tab = QtWidgets.QWidget()
    tab.brain_widget = None                      # the loader only keeps it
    bar = QtWidgets.QHBoxLayout(tab)
    add_load_brain_button(tab, bar)
    load, reset = tab.load_brain_button, tab.reset_brain_button
    assert load.text() == '\U0001F4BE'                               # a floppy disk
    assert 'Dosidicus Line Emoji' in load.styleSheet()               # plain, the same everywhere
    assert load.toolTip() == 'Load a custom brain architecture'      # tooltips kept
    assert reset.toolTip() == 'Reset to default brain'
    assert load.size() == reset.size() == tab._brain_buttons_size    # one size
    assert bar.spacing() == tab._brain_buttons_gap == 6              # close together
    # Side by side, Load then Reset, at the right-hand end as before.
    assert bar.indexOf(reset) == bar.indexOf(load) + 1 == bar.count() - 1
    # The Brain Designer button above them is that size too, with its tooltip.
    text = (ROOT / 'src' / 'brain_network_tab.py').read_text(encoding='utf-8')
    assert text.count('DisplayScaling.scale(100), DisplayScaling.scale(80)') == 2
    assert 'setToolTip(loc.get("tooltip_brain_designer"))' in text


def test_the_brain_button_is_as_far_above_reset_as_reset_is_from_load():
    """One gap, both ways: the Brain Designer button sits at the bottom of
    its row, so the space down to Reset is the tab's row spacing - which is
    also the spacing set between Reset and Load."""
    text = (ROOT / 'src' / 'brain_network_tab.py').read_text(encoding='utf-8')
    assert ('self.stats_and_button_layout.addWidget(self.new_button_container, 0,\n'
            '                                               QtCore.Qt.AlignBottom)') in text
    loader = (ROOT / 'src' / 'custom_brain_loader.py').read_text(encoding='utf-8')
    assert 'checkbox_layout.setSpacing(network_tab._brain_buttons_gap)' in loader
    assert 'gap = tab_layout.spacing()' in loader


# ---- the decoration window opens in the bottom right, however it is opened ----
def test_the_decoration_window_goes_bottom_right_each_time_it_is_shown(monkeypatch):
    import os
    from PyQt5 import QtCore, QtWidgets
    from src import desktop_style
    from src.ui import DecorationWindow
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setenv(desktop_style.SCREEN_OVERRIDE, '1920x1080')
    asked = []
    monkeypatch.setattr(desktop_style, 'place_exactly',
                        lambda window, x, y, **k: (asked.append((x, y)), window.move(x, y)))
    window = DecorationWindow()
    try:
        area = desktop_style.layout_area(QtWidgets.QApplication.primaryScreen())
        window.show()                       # from the menu, with D, or as the game starts
        QtWidgets.QApplication.processEvents()
        assert asked, 'showing it did not place it'
        x, y = asked[-1]
        frame = window.frameGeometry()
        assert x == area.right() - max(frame.width(), window.width()) - window.CORNER_GAP
        assert y == area.bottom() - max(frame.height(), window.height()) - window.CORNER_GAP
        # Its far corner sits in the corner of the area, whatever size it is.
        assert x + max(frame.width(), window.width()) == area.right() - window.CORNER_GAP
        assert y + max(frame.height(), window.height()) == area.bottom() - window.CORNER_GAP

        window.hide()
        window.move(100, 100)               # somewhere it was left, hidden: not the player's doing
        asked.clear()
        window.show()
        QtWidgets.QApplication.processEvents()
        assert asked and asked[-1] == (x, y)

        window.move(300, 200)               # the player drags it away while it is open
        window.hide()
        asked.clear()
        window.show()
        QtWidgets.QApplication.processEvents()
        assert asked == [] and (window.pos().x(), window.pos().y()) == (300, 200)
    finally:
        window.close()


# ---- a save never stops the game ---------------------------------------------
def test_an_autosave_that_fails_is_skipped_and_the_game_goes_on(capsys):
    from src.tamagotchi_logic import TamagotchiLogic

    class Game:
        def save_game(self, is_autosave=False):
            raise ValueError('Connection references an unknown neuron: is_sick -> cleanliness')
    TamagotchiLogic.autosave(Game())            # must not raise
    assert 'Autosave failed and was skipped' in capsys.readouterr().out


def test_a_connection_to_something_that_is_not_a_neuron_is_left_out_of_the_save():
    import inspect
    from src import brain_tool
    source = inspect.getsource(brain_tool.SquidBrainWindow.get_brain_state)
    assert 'k[0] in known and k[1] in known' in source
    from src.brain_io import normalise_brain
    import pytest
    with pytest.raises(ValueError):             # what the save format does with one
        normalise_brain({'neurons': {'cleanliness': {'position': [0, 0]}},
                         'connections': [['is_sick', 'cleanliness', 0.2]]})
