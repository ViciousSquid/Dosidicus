"""Decisions tab, mirroring the desktop "How the squid decides" view.

Shows the winning action + a confidence read-out, then a bar per candidate
action: the filled bar is the final (adjusted) score, a faint tick marks the
base score before memory/personality modifiers, and the winner is ringed — so
the influence of memory/personality is visible at a glance.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp, sp

# action -> RGB, ported from the desktop ACTION_META.
ACTION_COLORS = {
    "exploring": (0.23, 0.51, 0.96),
    "eating": (0.96, 0.51, 0.13),
    "comfort": (0.13, 0.69, 0.38),
    "playing": (0.61, 0.35, 0.91),
    "sleeping": (0.39, 0.40, 0.94),
}


def _confidence(conf):
    conf = max(0.0, min(1.0, conf))
    if conf < 0.12:
        return "Torn", (0.90, 0.33, 0.24)
    if conf < 0.32:
        return "Leaning", (0.92, 0.55, 0.28)
    if conf < 0.6:
        return "Fairly sure", (0.94, 0.68, 0.25)
    if conf < 0.85:
        return "Confident", (0.55, 0.75, 0.30)
    return "Decisive", (0.13, 0.69, 0.42)


def _hex(rgb):
    return "".join(f"{int(c * 255):02x}" for c in rgb)


class _ActionBars(Widget):
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.sim = simulation
        self._labels = {}
        self.bind(pos=lambda *_: self.redraw(), size=lambda *_: self.redraw())

    def _label(self, key, text, size, bold=False):
        cached = self._labels.get(key)
        if cached is None or cached[1] != text:
            lbl = CoreLabel(text=text, font_size=size, bold=bold)
            lbl.refresh()
            self._labels[key] = (lbl.texture, text)
        return self._labels[key][0]

    def redraw(self, *args):
        self.canvas.clear()
        d = getattr(self.sim.squid, "last_decision", {}) or {}
        final = d.get("weights", {})
        base = d.get("base_weights", {})
        chosen = d.get("chosen")
        with self.canvas:
            Color(0.10, 0.12, 0.17, 1)
            Rectangle(pos=self.pos, size=self.size)
            if not final:
                return
            names = sorted(final, key=lambda n: final[n], reverse=True)
            max_final = max(list(final.values()) + [1.0])
            pad = dp(10)
            row_h = min(dp(46), (self.height - pad) / max(1, len(names)))
            label_w = self.width * 0.30
            bar_x = self.x + label_w
            bar_w = self.width - label_w - pad - dp(46)
            for i, name in enumerate(names):
                y = self.y + self.height - (i + 1) * row_h + row_h * 0.18
                bh = row_h * 0.5
                col = ACTION_COLORS.get(name, (0.5, 0.55, 0.62))

                # track
                Color(0.2, 0.22, 0.26, 1)
                Rectangle(pos=(bar_x, y), size=(bar_w, bh))
                # final (adjusted) fill
                frac = max(0.0, min(1.0, final[name] / max_final))
                Color(*col, 1)
                Rectangle(pos=(bar_x, y), size=(bar_w * frac, bh))
                # base tick (pre-modifier score)
                if name in base and max_final > 0:
                    gx = bar_x + bar_w * max(0.0, min(1.0, base[name] / max_final))
                    Color(1, 1, 1, 0.65)
                    Line(points=[gx, y, gx, y + bh], width=dp(1.2))
                # winner ring
                if name == chosen:
                    Color(1.0, 0.84, 0.0, 1)
                    Line(rectangle=(bar_x - dp(2), y - dp(2), bar_w + dp(4), bh + dp(4)),
                         width=dp(1.4))

                # action label
                tex = self._label(f"n{name}", name.capitalize(), sp(14), bold=(name == chosen))
                Color(0.92, 0.94, 0.97, 1)
                Rectangle(texture=tex, pos=(self.x + pad, y + bh / 2 - tex.height / 2),
                          size=tex.size)
                # value
                vtex = self._label(f"v{name}{int(final[name])}", str(int(final[name])), sp(13))
                Color(1, 1, 1, 0.85)
                Rectangle(texture=vtex, pos=(bar_x + bar_w + dp(6), y + bh / 2 - vtex.height / 2),
                          size=vtex.size)


class DecisionsPanel(BoxLayout):
    def __init__(self, simulation, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.sim = simulation
        self.header = Label(markup=True, size_hint_y=None, height=dp(110),
                            halign="left", valign="top", font_size=sp(15),
                            padding=(dp(12), dp(10)))
        self.header.bind(size=lambda *_: setattr(self.header, "text_size", self.header.size))
        self.add_widget(self.header)
        self.bars = _ActionBars(self.sim)
        self.add_widget(self.bars)

    def set_simulation(self, sim):
        self.sim = sim
        self.bars.sim = sim

    def refresh(self):
        s = self.sim.squid
        d = getattr(s, "last_decision", {}) or {}
        chosen = d.get("chosen", "…")
        conf = d.get("confidence", 0.0)
        clabel, ccol = _confidence(conf)
        acol = ACTION_COLORS.get(chosen, (0.7, 0.72, 0.78))
        mem = d.get("memory_mod", {})
        influenced = [k for k, v in mem.items() if abs(v - 1.0) > 0.02]
        infl = ("memory boosting " + ", ".join(influenced)) if influenced else "no active memory pull"
        self.header.text = (
            f"[b]How the squid decides[/b]  ([i]{s.personality.value}[/i])\n"
            f"Chose [b][color={_hex(acol)}]{chosen}[/color][/b] — "
            f"[i]{self.sim.last_status}[/i]\n"
            f"Confidence: [b][color={_hex(ccol)}]{clabel}[/color][/b] ({int(conf * 100)}%)   "
            f"[size=12sp][color=999999]{infl}[/color][/size]")
        self.bars.redraw()
