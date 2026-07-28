"""BrainView - the live, inspectable neural network.

Draws every neuron as a circle whose fill encodes its current activation and
every learned connection as a line whose colour (green = excitatory, red =
inhibitory) and thickness encode the weight. This is the "see it thinking" part
of Dosidicus, ported from the desktop ``brain_widget.py`` visualisation down to
what reads well on a phone. Grown (neurogenesis) neurons get a gold ring so you
can spot new structure at a glance.
"""

from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse
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
            lbl = CoreLabel(text=text, font_size=sp(12))
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

            # --- Connections (draw first, behind neurons) ---
            drawn = set()
            for (a, b), w in brain.weights.items():
                if (b, a) in drawn or a == b:
                    continue
                drawn.add((a, b))
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
                Line(points=[x1, y1, x2, y2], width=dp(0.5) + dp(2.6) * mag)

            # --- Neurons ---
            grown = set(brain.neurogenesis.get("new_neurons", []))
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
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))

                # Label.
                tex = self._text_texture(name.replace("_", " "))
                Color(1, 1, 1, 0.85)
                from kivy.graphics import Rectangle
                Rectangle(texture=tex, pos=(cx - tex.width / 2, cy + r + 1),
                          size=tex.size)
