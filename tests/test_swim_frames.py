"""Host and guest always swim with both frames, and never in step.

A visiting squid's drawing used to keep the frame its home sent - always the
first - so it never swam. Now the host draws it: always the resident's other
frame, turning when the resident's does, and on its own when the resident is
still. Drawing only; nothing about either squid changes.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5 import QtWidgets                                        # noqa: E402

from plugins.multiplayer.remote_entity_manager import RemoteEntityManager  # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Resident:
    current_frame = 0


def guest(resident=None):
    entities = RemoteEntityManager(QtWidgets.QGraphicsScene(), 1280, 900)
    entities.position_update_timer.stop()
    entities.swim_timer.stop()
    if resident is not None:
        entities.resident_frame = lambda: resident.current_frame
    entities.update_remote_squid('squid_abc123', {'x': 100., 'y': 300., 'direction': 'right',
                                                  'image_direction_key': 'right'},
                                 is_new_arrival=True)
    return entities, entities.remote_squids['squid_abc123']


def frame(info):
    return RemoteEntityManager._shown_frame(info)


def test_a_guest_swims_on_the_residents_other_frame_whenever_it_turns():
    resident = Resident()
    entities, info = guest(resident)
    assert frame(info) == 2                         # the resident shows frame 1
    for current in (1, 0, 1, 0):
        resident.current_frame = current
        entities._swim()
        assert frame(info) == (1 if current == 1 else 2)   # never the same


def test_a_guest_keeps_swimming_when_the_resident_is_still():
    resident = Resident()
    entities, info = guest(resident)
    entities._swim()
    shown = []
    for _ in range(4):
        info['swum_at'] -= entities.SWIM_SECONDS        # a second goes by
        entities._swim()
        shown.append(frame(info))
    assert shown == [1, 2, 1, 2]


def test_an_update_from_home_changes_facing_but_not_the_frame_drawn_here():
    resident = Resident()
    entities, info = guest(resident)
    entities.update_remote_squid('squid_abc123', {'x': 120., 'y': 300., 'image_direction_key': 'left',
                                                  'current_animation_frame': 1})
    assert info['current_image_name'] == 'left2.png'


def test_without_a_resident_a_guest_still_swims():
    entities, info = guest()
    first = frame(info)
    info['swum_at'] = 0.
    entities._swim()
    assert frame(info) == 3 - first
