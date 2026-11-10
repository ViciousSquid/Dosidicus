"""A squid keeps its colour in other tanks.

A player can give their squid a colour (About tab). It is part of what the
squid looks like, so it goes with the squid's identity to any tank it visits
and is drawn there exactly as its own tank draws it: a friend's pink squid
arrives pink.
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

from plugins.multiplayer.identity import SquidIdentity             # noqa: E402
from plugins.multiplayer.remote_entity_manager import RemoteEntityManager  # noqa: E402
from src import tint                                                # noqa: E402

PINK = (255, 105, 180)
UUID = '3f2b8c1e-5d47-4a9b-8e21-7c6d5b4a3f20'


def _colours(pixmap):
    """(painted pixels as a set of rgb, count of fully clear pixels)."""
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
    painted, clear = set(), 0
    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            colour = image.pixelColor(x, y)
            if colour.alpha() == 0:
                clear += 1
            elif colour.alpha() == 255:
                painted.add((colour.red(), colour.green(), colour.blue()))
    return painted, clear


def test_a_colour_is_three_numbers_or_nothing():
    assert tint.rgb_of(QtGui.QColor(*PINK)) == PINK
    assert tint.rgb_of(list(PINK)) == PINK
    for junk in (None, 'pink', [255, 105], [255, 105, 999], [1.5, 2, 3], [True, 0, 0],
                 {'r': 1}, QtGui.QColor()):
        assert tint.rgb_of(junk) is None


def test_the_colour_goes_with_the_squids_identity_and_junk_does_not():
    squid = SimpleNamespace(uuid=UUID, name='Rosa', personality='timid',
                            tint_color=QtGui.QColor(*PINK))
    identity = SquidIdentity.from_squid(squid)
    assert identity.tint == PINK
    payload = identity.to_payload()
    assert payload['tint'] == list(PINK)                 # plain numbers on the wire
    assert SquidIdentity.from_payload(payload).tint == PINK
    # No colour, an older game that sends none, and nonsense: all "no colour".
    assert SquidIdentity.from_squid(SimpleNamespace(uuid=UUID, tint_color=None)).tint is None
    for sent in ({}, {'tint': None}, {'tint': 'pink'}, {'tint': [300, 0, 0]},
                 {'tint': [0, 0]}):
        other = SquidIdentity.from_payload(dict(uuid=UUID, name='Rosa', **sent))
        assert other is not None and other.tint is None


def test_a_tinted_squid_is_washed_with_its_colour_and_keeps_its_shape():
    plain = QtGui.QPixmap(str(ROOT / 'images' / 'left1.png'))
    pink = tint.tinted(plain, PINK)
    assert pink.size() == plain.size()
    plain_colours, plain_clear = _colours(plain)
    pink_colours, pink_clear = _colours(pink)
    assert pink_clear == plain_clear                     # nothing painted outside it
    assert pink_colours != plain_colours
    # White parts of the drawing lean pink: red stays high, green drops.
    white = [c for c in pink_colours if c[0] > 240]
    assert white and all(c[1] < c[0] and c[1] < 250 for c in white)
    assert tint.tinted(plain, None) is plain


def _tank():
    entities = RemoteEntityManager(QtWidgets.QGraphicsScene(), 1280, 900)
    entities.position_update_timer.stop()
    entities.swim_timer.stop()
    return entities


def _arrive(entities, node, sent_tint='absent'):
    identity = {'uuid': UUID, 'name': 'Rosa', 'personality': 'timid'}
    if sent_tint != 'absent':
        identity['tint'] = sent_tint
    entities.update_remote_squid(node, {'x': 0., 'y': 300., 'image_direction_key': 'left',
                                        'identity': identity}, is_new_arrival=True)
    return entities.remote_squids[node]


def test_a_friends_pink_squid_is_pink_in_my_tank():
    entities = _tank()
    pink = _arrive(entities, 'squid_pink001', list(PINK))
    plain = _arrive(entities, 'squid_plain01')
    assert pink['tint'] == PINK and plain['tint'] is None
    pink_colours, _ = _colours(pink['visual'].pixmap())
    plain_colours, _ = _colours(plain['visual'].pixmap())
    assert pink_colours != plain_colours
    # Drawn as its own tank draws it: the same wash over the same picture.
    expected, _ = _colours(tint.tinted(entities._scaled_pixmap(pink['current_image_name'])[0], PINK))
    assert pink_colours == expected


def test_it_stays_pink_as_it_swims_turns_and_is_followed_round_the_tank():
    entities = _tank()
    info = _arrive(entities, 'squid_pink001', list(PINK))
    plain_right, _ = _colours(entities._scaled_pixmap('right1.png')[0])
    assert entities.follow_body('squid_pink001', 640., 420., 'right')     # it turns
    assert info['current_image_name'].startswith('right')
    assert _colours(info['visual'].pixmap())[0] != plain_right
    entities._show_frame(info, 2 if info['current_image_name'].endswith('1.png') else 1)
    assert info['tint'] == PINK                                           # the other swim frame
    plain_frame, _ = _colours(entities._scaled_pixmap(info['current_image_name'])[0])
    assert _colours(info['visual'].pixmap())[0] != plain_frame
    # An update that says nothing about colour leaves it as it is.
    entities.update_remote_squid('squid_pink001', {'x': 0., 'y': 300.,
                                                   'image_direction_key': 'right'})
    assert info['tint'] == PINK


def test_a_new_colour_given_while_it_is_out_is_seen():
    entities = _tank()
    info = _arrive(entities, 'squid_pink001', list(PINK))
    before, _ = _colours(info['visual'].pixmap())
    identity = {'uuid': UUID, 'name': 'Rosa', 'tint': [60, 120, 255]}
    entities.update_remote_squid('squid_pink001', {'x': 0., 'y': 300.,
                                                   'image_direction_key': 'left',
                                                   'identity': identity})
    assert info['tint'] == (60, 120, 255)
    assert _colours(info['visual'].pixmap())[0] != before
    identity['tint'] = None                              # and the colour taken off again
    entities.update_remote_squid('squid_pink001', {'x': 0., 'y': 300.,
                                                   'image_direction_key': 'left',
                                                   'identity': identity})
    assert info['tint'] is None


def test_the_colour_sent_is_the_squids_colour_now():
    """Read afresh for every message: a colour chosen after going online is
    the colour other tanks see."""
    from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
    plugin = MultiplayerPlugin()
    squid = SimpleNamespace(uuid=UUID, name='Rosa', personality='timid', tint_color=None)
    assert plugin._identity_now(squid)['tint'] is None
    squid.tint_color = QtGui.QColor(*PINK)
    assert plugin._identity_now(squid)['tint'] == list(PINK)
