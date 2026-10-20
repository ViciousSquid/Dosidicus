"""BrainView - the live, inspectable neural network.

Draws every neuron as a circle whose fill encodes its current activation and
every learned connection as a line whose colour (green = excitatory, red =
inhibitory) and thickness encode the weight. This is the "see it thinking" part
of Dosidicus, ported from the desktop ``brain_widget.py`` visualisation down to
what reads well on a phone. Grown (neurogenesis) neurons get a gold ring so you
can spot new structure at a glance.
"""

from math import cos, radians, sin

from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse, Mesh
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp, sp

from ..engine import constants

VW, VH = constants.VIRTUAL_CANVAS  # virtual coordinate space of neuron positions


def _heat(activation):
    """Map a 0-100 activation onto a cool->warm fill colour."""
    a = max(0.0, min(1.0, activation / 100.0))
    # blue (cold) -> teal -> amber -> red (hot)
    r = min(1.0, a * 1.8)
    g = min(1.0, 0.3 + a * 0.5)
    b = max(0.1, 1.0 - a * 1.4)
    return (r, g, b)


class BrainView(Widget):
    def __init__(self, brain=None, **kwargs):
        super().__init__(**kwargs)
        self.brain = brain
        self._label_cache = {}
        self.bind(pos=lambda *a: self.redraw(), size=lambda *a: self.redraw())

    def set_brain(self, brain):
        self.brain = brain
        self.redraw()

    # Map a virtual (0-VW, 0-VH) point into widget space (y flipped for canvas).
    def _map(self, vx, vy):
        pad = dp(26)
        w = max(1, self.width - 2 * pad)
        h = max(1, self.height - 2 * pad)
        x = self.x + pad + (vx / VW) * w
        y = self.y + pad + (1.0 - vy / VH) * h
        return x, y

    def _text_texture(self, text):
        tex = self._label_cache.get(text)
        if tex is None:
            lbl = CoreLabel(text=text, font_size=sp(10), text_size=(dp(42), None), halign='center')
            lbl.refresh()
            tex = lbl.texture
            self._label_cache[text] = tex
        return tex

    def redraw(self, *args):
        self.canvas.clear()
        if not self.brain:
            return
        brain = self.brain
        with self.canvas:
            # Background.
            Color(0.06, 0.08, 0.13, 1)
            from kivy.graphics import Rectangle
            Rectangle(pos=self.pos, size=self.size)

            # The canonical desktop row geometry makes the motor bank legible.
            # The social band only once something social has grown.
            from src.brain_constants import display_rows
            for row in display_rows(brain.neuron_positions).values():
                _, upper = self._map(0, row['band'][0])
                _, lower = self._map(0, row['band'][1])
                Color(.25, .30, .44, .16)
                Rectangle(pos=(self.x+dp(6), lower), size=(self.width-dp(12), upper-lower))
                tex = self._text_texture(row['label'])
                Color(.65, .72, .86, .8)
                Rectangle(texture=tex, pos=(self.x+dp(8), upper-tex.height), size=tex.size)

            # --- Connections (draw first, behind neurons) ---
            for (a, b), w in brain.weights.items():
                if a == b:
                    continue
                if a not in brain.neuron_positions or b not in brain.neuron_positions:
                    continue
                mag = min(1.0, abs(w))
                if mag < 0.03:
                    continue
                x1, y1 = self._map(*brain.neuron_positions[a])
                x2, y2 = self._map(*brain.neuron_positions[b])
                if w >= 0:
                    Color(0.2, 0.9, 0.4, 0.15 + 0.6 * mag)   # excitatory green
                else:
                    Color(0.95, 0.3, 0.3, 0.15 + 0.6 * mag)  # inhibitory red
                import math
                dx, dy = x2 - x1, y2 - y1
                length = math.hypot(dx, dy) or 1
                # Offset reciprocal edges so opposite signs remain visible.
                offset = dp(3) if (b, a) in brain.weights else 0
                ox, oy = -dy / length * offset, dx / length * offset
                Line(points=[x1+ox, y1+oy, x2+ox, y2+oy], width=dp(0.5) + dp(2.6) * mag)
                ax, ay = x1 + dx * .72 + ox, y1 + dy * .72 + oy
                ux, uy = dx / length, dy / length
                Line(points=[ax-ux*dp(7)-uy*dp(4), ay-uy*dp(7)+ux*dp(4),
                             ax, ay, ax-ux*dp(7)+uy*dp(4), ay-uy*dp(7)-ux*dp(4)], width=dp(1))

            # --- Neurons ---
            grown = set(brain.neurogenesis.get("new_neurons", []))
            label_boxes = []
            for name, (vx, vy) in brain.neuron_positions.items():
                cx, cy = self._map(vx, vy)
                act = brain.state.get(name, 0.0)
                r = dp(11) if name in constants.CORE_NEURONS else dp(9)
                if name in grown:
                    r = dp(10)
                ring = dp(3)

                # Rings: gold for grown neurons, blue for sensors, grey core.
                if name in grown:
                    Color(1.0, 0.84, 0.0, 1)
                    Ellipse(pos=(cx - r - ring, cy - r - ring),
                            size=(2 * (r + ring), 2 * (r + ring)))
                elif constants.is_sensor(name):
                    Color(0.39, 0.58, 0.93, 1)
                    Ellipse(pos=(cx - r - ring, cy - r - ring),
                            size=(2 * (r + ring), 2 * (r + ring)))

                # Fill.
                if constants.is_binary(name):
                    on = act > 50
                    Color(0.2, 0.9, 0.3, 1) if on else Color(0.35, 0.1, 0.1, 1)
                else:
                    Color(*_heat(act), 1)
                if constants.is_social(name):
                    # A social neuron is a hexagon, as on desktop.
                    corners = [(cx + r * cos(radians(60 * i - 90)),
                                cy + r * sin(radians(60 * i - 90))) for i in range(7)]
                    vertices = [cx, cy, 0, 0] + [v for x, y in corners for v in (x, y, 0, 0)]
                    Mesh(vertices=vertices, indices=list(range(len(corners) + 1)),
                         mode='triangle_fan')
                else:
                    Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))

                # Label.
                aliases = {'happiness':'happy', 'cleanliness':'clean', 'sleepiness':'tired',
                    'satisfaction':'sated', 'curiosity':'curious', 'can_see_food':'food seen',
                    'external_stimulus':'novelty', 'is_sleeping':'asleep',
                    'is_startled':'startled', 'threat_level':'threat'}
                tex = self._text_texture(aliases.get(name, name.replace('act_', '').replace('_', ' ')))
                Color(1, 1, 1, 0.85)
                from kivy.graphics import Rectangle
                left = cx - tex.width / 2
                candidates = (cy+r+1, cy-r-tex.height-1,
                              cy+r+dp(24), cy-r-tex.height-dp(24))
                for bottom in candidates:
                    box = (left, bottom, left+tex.width, bottom+tex.height)
                    if not any(box[0] < old[2] and box[2] > old[0]
                               and box[1] < old[3] and box[3] > old[1] for old in label_boxes):
                        break
                label_boxes.append(box)
                Rectangle(texture=tex, pos=(left, bottom), size=tex.size)

    def on_touch_down(self, touch):
        if self.brain and self.collide_point(*touch.pos) and touch.is_double_tap:
            from math import hypot
            nearest = min(self.brain.positions, key=lambda n: hypot(
                self._map(*self.brain.positions[n])[0] - touch.x,
                self._map(*self.brain.positions[n])[1] - touch.y))
            cx, cy = self._map(*self.brain.positions[nearest])
            if hypot(cx-touch.x, cy-touch.y) < dp(32):
                from .menu import _message
                rows = [f'Activation: {self.brain.state.get(nearest, 0):.1f}%',
                        self.brain.explain_neuron(nearest)]
                for edge, weight in self.brain.weights.items():
                    if nearest in edge:
                        rows.append(f'{edge[0]} -> {edge[1]}: {weight:+.3f}')
                _message(nearest, '\n'.join(rows))
                return True
        return super().on_touch_down(touch)
