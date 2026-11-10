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


def test_every_head_icon_sits_just_above_the_squid_at_any_tank_size():
    for screen in ((2880, 1920), (2560, 1440), (1920, 1080)):
        saved = _with_screen(*screen)
        try:
            scene = QtWidgets.QGraphicsScene()
            squid = _squid(scene)
            icon_image = D.to_points(QtGui.QPixmap(72, 90))          # ng.png, sick.png, curious.png
            places = []
            for name in ('ng_icon', 'startled_icon', 'sick_icon_item'):
                icon = scene.addPixmap(icon_image)
                setattr(squid, name, icon)
            squid.update_head_icon_positions()
            for name in ('ng_icon', 'startled_icon', 'sick_icon_item'):
                icon = getattr(squid, name)
                bottom = icon.y() + icon.pixmap().height()
                gap = squid.squid_y - bottom
                places.append((icon.x(), icon.y()))
                # A small gap, the same share of the tank on every screen -
                # not the 54 pixels it floated at on a 1080p screen.
                assert gap == D.points(10) and 0 < gap <= 10, (screen, name, gap)
            assert len({y for _x, y in places}) == 1                 # all at one height
            assert len({x for x, _y in places}) == 3                 # side by side, not stacked
            left = min(x for x, _y in places)
            right = max(x for x, _y in places) + icon_image.width()
            assert abs((left + right) / 2 - (squid.squid_x + squid.squid_width / 2)) <= 1
        finally:
            _restore(saved)


def test_the_curious_and_sick_icons_are_placed_the_same_way():
    from src.mental_states import MentalStateManager
    scene = QtWidgets.QGraphicsScene()
    squid = _squid(scene)
    manager = MentalStateManager(squid, scene)
    squid.mental_state_manager = manager
    manager.set_state('sick', True)
    sick = manager.mental_states['sick'].icon_item
    ng = scene.addPixmap(sick.pixmap())
    squid.ng_icon = ng
    squid.update_head_icon_positions()
    assert ng.y() == sick.y()                    # the same height above the head
    assert ng.x() != sick.x()                    # beside each other
    # One of them alone sits exactly over the middle of the squid.
    manager.set_state('sick', False)
    squid.update_head_icon_positions()
    centre = ng.x() + ng.pixmap().width() / 2
    assert abs(centre - (squid.squid_x + squid.squid_width / 2)) <= 1
    # And when the squid moves, every one of them moves with it at once.
    manager.set_state('curious', True)
    squid.squid_x += 90
    squid.update_head_icon_positions()
    curious = manager.mental_states['curious'].icon_item
    middle = (min(ng.x(), curious.x()) + max(ng.x(), curious.x()) + ng.pixmap().width()) / 2
    assert abs(middle - (squid.squid_x + squid.squid_width / 2)) <= 1


def test_a_squid_that_swims_out_takes_its_head_icons_with_it():
    from src.mental_states import MentalStateManager
    scene = QtWidgets.QGraphicsScene()
    squid = _squid(scene)
    manager = MentalStateManager(squid, scene)
    squid.mental_state_manager = manager
    manager.set_state('sick', True)
    squid.ng_icon = scene.addPixmap(QtGui.QPixmap(72, 90))
    squid.update_head_icon_positions()
    sick = manager.mental_states['sick'].icon_item
    assert squid.ng_icon.isVisible() and sick.isVisible()
    squid.set_in_tank(False)                     # it has left for another tank
    assert not squid.squid_item.isVisible()
    assert not squid.ng_icon.isVisible() and not sick.isVisible()
    squid.set_in_tank(True)                      # and come home
    assert squid.ng_icon.isVisible() and sick.isVisible()
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
