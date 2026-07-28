"""Learning tab rendered as connection cards, like the desktop Learning tab.

Each recent weight change is a card: NEURON1 -> NEURON2 with the weight delta,
an LTP (potentiation, green) or LTD (depression, red) badge, whether it came
from Hebbian or STDP learning, the resulting weight, and a timestamp. A header
summarises the learning rate, neurogenesis boost and STDP activity.
"""

from datetime import datetime

from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp, sp

from .memory_cards import _Card

_GREEN = ((0.82, 1.0, 0.82), (0.05, 0.2, 0.05))     # LTP / potentiation
_PINK = ((1.0, 0.82, 0.86), (0.25, 0.05, 0.1))      # LTD / depression
_BLUE = ((0.25, 0.41, 0.88), (1, 1, 1))             # neurogenesis


def _strength(w):
    m = abs(w)
    return ("very strong" if m > 0.8 else "strong" if m > 0.5 else
            "moderate" if m > 0.25 else "weak")


class LearningCards(ScrollView):
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.sim = simulation
        self.box = BoxLayout(orientation="vertical", size_hint_y=None,
                             spacing=dp(6), padding=dp(8))
        self.box.bind(minimum_height=self.box.setter("height"))
        self.add_widget(self.box)

    def _header(self):
        b = self.sim.squid.brain
        boost = "ACTIVE x1.5" if b.neurogenesis_active else "off"
        txt = (f"[b][color=b39ddb]Hebbian + STDP learning[/color][/b]\n"
               f"Rate [b]{b.config['base_learning_rate']}[/b]/s   "
               f"threshold [b]{int(b.config['co_activation_threshold']*100)}%[/b]   "
               f"neurogenesis boost [b]{boost}[/b]\n"
               f"[color=b39ddb]STDP[/color] timing-strengthenings: [b]{b.stdp_potentiations}[/b]")
        lbl = Label(text=txt, markup=True, size_hint_y=None, halign="left",
                    valign="top", color=(0.9, 0.92, 0.95, 1), font_size=sp(14))
        lbl.bind(width=lambda *_: setattr(lbl, "text_size", (lbl.width, None)),
                 texture_size=lambda *_: setattr(lbl, "height", lbl.texture_size[1] + dp(6)))
        return lbl

    def _card(self, e):
        t = e.get("t", 0)
        ts = datetime.fromtimestamp(t).strftime("%H:%M:%S") if t else ""
        if e.get("born"):
            text = (f"[b]Neurogenesis[/b]  grew [b]{e['a']}[/b]\n"
                    f"[size=12sp]wired to {e['b']}   {ts}[/size]")
            return _Card(text, _BLUE[0], _BLUE[1])
        dw = e.get("dw", 0.0)
        w = e.get("weight", 0.0)
        potentiation = dw >= 0
        bg, fg = (_GREEN if potentiation else _PINK)
        kind = "LTP" if potentiation else "LTD"
        rule = "STDP" if e.get("stdp") else "Hebbian"
        sign = "+" if dw >= 0 else ""
        arrow = "->"
        text = (f"[b]{e['a']}[/b]  {arrow}  [b]{e['b']}[/b]\n"
                f"[size=12sp]{kind} · {rule}   Δ{sign}{dw:.3f}   "
                f"w={w:+.2f} ({_strength(w)})   {ts}[/size]")
        return _Card(text, bg, fg)

    def refresh(self):
        self.box.clear_widgets()
        self.box.add_widget(self._header())
        events = list(reversed(self.sim.squid.brain.recent_events[-24:]))
        if not events:
            hint = Label(text="No learning yet — care for your squid and watch "
                         "connections change.", size_hint_y=None, height=dp(40),
                         halign="left", valign="middle", color=(0.6, 0.6, 0.65, 1),
                         font_size=sp(13))
            hint.bind(size=lambda *_: setattr(hint, "text_size", hint.size))
            self.box.add_widget(hint)
        for e in events:
            self.box.add_widget(self._card(e))
