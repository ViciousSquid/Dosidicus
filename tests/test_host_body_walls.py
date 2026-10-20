"""A visitor's body in the host tank arrives facing in, and walls turn it.

Found by the three-tank LAN run (tools/test_lan_round_trip.py): a visitor let
in at the right side faced right, into the glass, and its exploring - "keep
going the way you are pointed" - pressed it against the wall for the whole
visit, its back to the resident it never saw.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_remote_mind_stage1 import Encounter, quiet_brain          # noqa: E402


def test_a_visitor_let_in_at_either_side_faces_into_the_tank():
    right = Encounter()
    assert right.admit(x=1250., y=400.).facing == 'left'
    left = Encounter()
    assert left.admit(x=10., y=400.).facing == 'right'


def test_a_wall_turns_an_exploring_visitor_and_it_comes_to_see_the_resident():
    meeting = Encounter()                                # resident at x=600
    actor = meeting.admit(x=1270., y=400.)
    actor.facing = 'right'                               # pressed to the glass
    meeting.set_brain(**quiet_brain(act_move=90.))
    seen = []
    for _ in range(12):
        meeting.cycle()
        seen.append(meeting.host_body.build_frame(actor).sensors.get('squid_in_view'))
    assert actor.facing == 'left' and actor.x < 1270.
    assert 100.0 in seen
