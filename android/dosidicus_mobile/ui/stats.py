"""StatsPanel - the seven core need/emotion bars."""

from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.core.text import Label as CoreLabel

# For these stats a HIGH value is bad, so the bar turns red as it fills.
INVERTED = {"hunger", "sleepiness", "anxiety"}

ROWS = ["hunger", "happiness", "cleanliness", "sleepiness",
        "satisfaction", "anxiety", "curiosity"]


class StatsPanel(Widget):
    def __init__(self, squid=None, **kwargs):
        super().__init__(**kwargs)
        self.squid = squid
        self._labels = {}
        self.bind(pos=lambda *a: self.redraw(), size=lambda *a: self.redraw())

    def set_squid(self, squid):
        self.squid = squid

    def _label(self, key, text, size):
        cached = self._labels.get(key)
        if cached is None or cached[1] != text:
            lbl = CoreLabel(text=text, font_size=size, bold=True)
            lbl.refresh()
            self._labels[key] = (lbl.texture, text)
        return self._labels[key][0]

    def redraw(self, *args):
        self.canvas.clear()
        if not self.squid:
            return
        n = len(ROWS)
        pad = 8
        row_h = (self.height - pad) / n
        label_w = self.width * 0.32
        bar_x = self.x + label_w
        bar_w = self.width - label_w - pad * 2
        with self.canvas:
            Color(0.10, 0.12, 0.17, 1)
            Rectangle(pos=self.pos, size=self.size)
            for i, name in enumerate(ROWS):
                val = getattr(self.squid, name, 0.0)
                y = self.y + self.height - (i + 1) * row_h + row_h * 0.2
                bh = row_h * 0.55

                # Track.
                Color(0.2, 0.22, 0.26, 1)
                Rectangle(pos=(bar_x, y), size=(bar_w, bh))

                # Fill colour by goodness.
                frac = max(0.0, min(1.0, val / 100.0))
                good = (1.0 - frac) if name in INVERTED else frac
                Color(1.0 - good, 0.55 + 0.35 * good, 0.25 + 0.25 * good, 1)
                Rectangle(pos=(bar_x, y), size=(bar_w * frac, bh))

                # Label + value.
                tex = self._label(f"lab{name}", name.capitalize(), 13)
                Color(0.9, 0.92, 0.95, 1)
                Rectangle(texture=tex, pos=(self.x + pad, y + bh / 2 - tex.height / 2),
                          size=tex.size)
                vtex = self._label(f"val{name}{int(val)}", str(int(val)), 12)
                Color(1, 1, 1, 0.9)
                Rectangle(texture=vtex,
                          pos=(bar_x + bar_w - vtex.width - 4, y + bh / 2 - vtex.height / 2),
                          size=vtex.size)
