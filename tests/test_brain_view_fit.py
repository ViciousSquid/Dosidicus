"""The brain view fits what the squid has, and draws back as it grows.

The network was fitted to the whole logical canvas - the three rows a squid
is born with and all of the growth space under them - so a newborn's network
sat in the top half of the Brain Tool over a blank bottom half. It is now
fitted to the part of the canvas that has something in it: the rows always,
the growth space as far as the squid has grown into it. When a neuron grows
outside what is shown, the view eases back to take it in. It follows the
widget's size, as it always did.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtWidgets                                 # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from src import brain_constants as bc                               # noqa: E402
from src.brain_widget import BrainWidget                            # noqa: E402

NEWBORN = {'hunger': (96.0, 100.0), 'curiosity': (928.0, 100.0),
           'can_see_food': (96.0, 258.0), 'act_move': (96.0, 406.0),
           'act_collapse': (928.0, 406.0)}


def on_screen(point, width, height, bounds):
    scale, dx, dy, _fit = bc.view_transform(width, height, bounds=bounds)
    return point[0] * scale + dx, point[1] * scale + dy


def test_a_newborns_view_is_its_three_rows_not_the_whole_canvas():
    x0, y0, x1, y1 = bc.content_bounds(NEWBORN)
    rows = bc.NEURON_ROWS
    assert (x0, x1) == (0.0, bc.LOGICAL_CANVAS[0])
    assert y0 <= rows['core']['band'][0] and y1 >= rows['motor']['band'][1]
    assert y1 < bc.GROWTH_ZONE[1] + 40                    # none of the empty growth space
    assert (y1 - y0) < 0.65 * bc.LOGICAL_CANVAS[1]


def test_the_view_takes_in_the_growth_space_as_it_is_used():
    newborn = bc.content_bounds(NEWBORN)
    grown = bc.content_bounds(dict(NEWBORN, can_see_plant=(512.0, 552.0)))
    assert grown[3] > newborn[3] and grown[3] >= 552.0 + bc.NEURON_REACH
    assert grown[:3] == newborn[:3]                       # only the bottom moved
    deeper = bc.content_bounds(dict(NEWBORN, can_see_plant=(512.0, 552.0),
                                    novelty_1=(300.0, 700.0)))
    assert deeper[3] > grown[3]
    # A social neuron brings its whole row into view.
    social = bc.content_bounds(dict(NEWBORN, can_see_squid=(200.0, 694.0)))
    assert social[3] >= bc.SOCIAL_ROW['band'][1]


def test_what_is_shown_fills_the_widget_and_stays_inside_it():
    for width, height in ((942, 362), (1242, 722), (600, 600), (400, 300)):
        bounds = bc.content_bounds(NEWBORN)
        scale, _dx, _dy, fit = bc.view_transform(width, height, bounds=bounds)
        whole, *_ = bc.view_transform(width, height)
        assert scale == fit
        # Fitted exactly: one of the two directions is used up...
        used_w = (bounds[2] - bounds[0]) * scale
        used_h = (bounds[3] - bounds[1]) * scale
        assert abs(used_w - width) < 1.0 or abs(used_h - height) < 1.0
        assert used_w <= width + 0.01 and used_h <= height + 0.01
        # ...centred in the other...
        left, top = on_screen((bounds[0], bounds[1]), width, height, bounds)
        right, bottom = on_screen((bounds[2], bounds[3]), width, height, bounds)
        assert abs(left - (width - right)) < 1.0 and abs(top - (height - bottom)) < 1.0
        # ...and never smaller than it was drawn before.
        assert scale >= whole - 1e-9
        # Every neuron is on the widget.
        for place in NEWBORN.values():
            x, y = on_screen(place, width, height, bounds)
            assert 0 <= x <= width and 0 <= y <= height
    # A short, wide Brain Tool is where it mattered: nearly twice the size.
    newborn = bc.view_transform(942, 362, bounds=bc.content_bounds(NEWBORN))[0]
    assert newborn > 1.5 * bc.view_transform(942, 362)[0]


def test_with_no_bounds_the_whole_canvas_is_fitted_as_before():
    scale, dx, dy, fit = bc.view_transform(1024, 768)
    assert (scale, dx, dy, fit) == (1.0, 0.0, 0.0, 1.0)
    scale, dx, dy, _fit = bc.view_transform(2048, 768, zoom=2.0, pan=(5.0, 7.0))
    assert (scale, dx, dy) == (2.0, 512.0 + 5.0, 7.0)


class View(QtCore.QObject):
    """Just the part of a BrainWidget that keeps the view."""
    VIEW_EASE = BrainWidget.VIEW_EASE
    VIEW_EASE_MS = BrainWidget.VIEW_EASE_MS
    _view_bounds = BrainWidget._view_bounds
    _ease_view_bounds = BrainWidget._ease_view_bounds
    _view_transform = BrainWidget._view_transform

    def __init__(self, positions):
        super().__init__()
        self.neuron_positions = dict(positions)
        self.dragging = False
        self.view_zoom, self.view_pan = 1.0, (0.0, 0.0)
        self.changes = []

    def width(self):
        return 942

    def height(self):
        return 362

    def _view_changed(self):
        self.changes.append(1)


def widget(positions):
    return View(positions)


def restore(_w):
    pass


def test_the_view_eases_back_when_a_neuron_grows_and_does_not_jump():
    w = widget(NEWBORN)
    try:
        start = w._view_bounds()
        assert start == bc.content_bounds(NEWBORN)
        scale_before = w._view_transform()[0]
        w.neuron_positions['can_see_plant'] = (512.0, 552.0)        # it grows a neuron
        target = bc.content_bounds(w.neuron_positions)
        assert w._view_bounds() == start                            # not at once...
        assert w._bounds_timer.isActive()
        bottoms = [start[3]]
        for _ in range(60):                                         # ...but step by step
            if not w._bounds_timer.isActive():
                break
            w._ease_view_bounds()
            bottoms.append(w._view_bounds()[3])
        assert bottoms == sorted(bottoms) and len(bottoms) > 6      # steadily, over many steps
        assert w._view_bounds() == target and not w._bounds_timer.isActive()
        assert w._view_transform()[0] < scale_before                # drawn back to make room
        assert len(w.changes) >= len(bottoms) - 1                   # and redrawn at each step
    finally:
        restore(w)


def test_the_view_holds_still_while_a_neuron_is_being_dragged():
    w = widget(NEWBORN)
    try:
        start = w._view_bounds()
        w.dragging = True
        w.neuron_positions['act_move'] = (96.0, 760.0)              # dragged far down
        assert w._view_bounds() == start                            # the view does not chase it
        assert getattr(w, '_bounds_timer', None) is None
        w.dragging = False                                          # let go: now it follows
        w._view_bounds()
        assert w._bounds_timer.isActive()
        w._bounds_timer.stop()
    finally:
        restore(w)


def test_the_drawing_and_the_hit_testing_use_the_same_view():
    worker = (ROOT / 'src' / 'brain_render_worker.py').read_text(encoding='utf-8')
    assert "getattr(state, 'bounds', None))" in worker               # what is drawn
    assert "state.bounds = shown() if callable(shown) else None" in worker
    assert "getattr(state, 'bounds', None)," in worker               # and its cache knows
    widget_source = (ROOT / 'src' / 'brain_widget.py').read_text(encoding='utf-8')
    assert widget_source.count('self._view_bounds())') == 2          # what is clicked, and zoomed
