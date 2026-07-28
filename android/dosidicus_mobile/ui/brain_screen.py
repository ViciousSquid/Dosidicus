"""BrainScreen - the tabbed brain inspector.

Mobile analogue of the desktop "Brain Tool" tabbed window. A scrollable strip of
tabs sits above a content area; the tabs mirror the desktop ones:

    Network | Learning | Memory | Decisions | Personality | Stats | About

* Network     - the live neuron/connection visualisation (BrainView canvas).
* Learning    - learning rate, neurogenesis boost, and a live feed of the most
                recent Hebbian weight changes.
* Memory      - the brain's strongest learned associations (long-term memory)
                and the neurons grown by neurogenesis (episodic milestones).
* Decisions   - the latest decision trace: every candidate action, its weight,
                the winner and the confidence.
* Personality - the squid's personality, description and its learning/stat biases.
* Stats       - neuron/connection counts, births by type, age, live stat values.
* About       - what the brain is and a legend for the visualisation.

Text tabs are throttled to a few refreshes per second; the Network canvas
redraws every frame while visible.
"""

import time

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.scatterlayout import ScatterLayout
from kivy.graphics.transformation import Matrix
from kivy.core.window import Window
from kivy.metrics import dp, sp

from .brainview import BrainView
from .memory_cards import MemoryCards
from .learning_cards import LearningCards
from .decisions_panel import DecisionsPanel
from ..engine.personality import (
    describe, PERSONALITY_STAT_MODIFIERS, PERSONALITY_LEARNING_MODIFIERS,
)

TABS = ["Network", "Learning", "Memory", "Decisions", "Personality", "Stats", "About"]

ACCENT = (0.5, 0.3, 0.6, 1)
ACCENT_OFF = (0.22, 0.18, 0.28, 1)


class _ScrollText(ScrollView):
    """A vertically scrolling markup label that fills the content area."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.label = Label(
            text="", markup=True, size_hint_y=None, halign="left", valign="top",
            padding=(dp(14), dp(12)), color=(0.92, 0.94, 0.97, 1), font_size=sp(15))
        self.label.bind(
            width=lambda *_: setattr(self.label, "text_size", (self.label.width, None)),
            texture_size=lambda *_: setattr(self.label, "height", self.label.texture_size[1]),
        )
        self.add_widget(self.label)

    def set_text(self, text):
        self.label.text = text


class BrainScreen(BoxLayout):
    TEXT_REFRESH = 0.35  # seconds between text-tab refreshes

    # Below this width (dp) we treat the device as a phone (vertical tabs).
    TABLET_MIN_WIDTH = 600

    def __init__(self, simulation, **kwargs):
        super().__init__(spacing=0, **kwargs)
        self.sim = simulation
        self.active = "Network"
        self._last_text_refresh = 0.0

        # Views shared across layouts.
        self.network = BrainView(self.sim.squid.brain)
        self.network_scatter = ScatterLayout(
            do_rotation=False, do_translation=True, do_scale=True,
            scale_min=0.5, scale_max=6.0)
        self.network_scatter.add_widget(self.network)
        self.textpanel = _ScrollText()
        self.memory_cards = MemoryCards(self.sim)
        self.learning_cards = LearningCards(self.sim)
        self.decisions_panel = DecisionsPanel(self.sim)

        # Responsive tab strip: a horizontal strip on tablets, a vertical
        # column on phones (where a top strip would be too cramped).
        self.is_tablet = Window.width >= dp(self.TABLET_MIN_WIDTH)
        self._tab_buttons = {}
        self.orientation = "vertical" if self.is_tablet else "horizontal"

        if self.is_tablet:
            strip = ScrollView(size_hint_y=None, height=dp(46), do_scroll_y=False,
                               bar_width=0)
            row = BoxLayout(orientation="horizontal", size_hint_x=None,
                            spacing=dp(2), padding=(dp(2), dp(2)))
            row.bind(minimum_width=row.setter("width"))
            for name in TABS:
                row.add_widget(self._make_tab(name, horizontal=True))
            strip.add_widget(row)
            self.add_widget(strip)
            self.content = BoxLayout(size_hint_y=1)
        else:
            col_scroll = ScrollView(size_hint_x=None, width=dp(96),
                                    do_scroll_x=False, bar_width=0)
            col = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(2), padding=(dp(2), dp(2)))
            col.bind(minimum_height=col.setter("height"))
            for name in TABS:
                col.add_widget(self._make_tab(name, horizontal=False))
            col_scroll.add_widget(col)
            self.add_widget(col_scroll)
            self.content = BoxLayout(size_hint_x=1)

        self.add_widget(self.content)
        self.select("Network")

    def set_simulation(self, sim):
        self.sim = sim
        self.memory_cards.sim = sim
        self.learning_cards.sim = sim
        self.decisions_panel.set_simulation(sim)
        self.network.set_brain(sim.squid.brain)
        self.select(self.active)

    def _make_tab(self, name, horizontal):
        if horizontal:
            b = Button(text=name, size_hint_x=None, width=dp(104), font_size=sp(14),
                       bold=True, background_normal="", background_color=ACCENT_OFF)
        else:
            b = Button(text=name, size_hint_y=None, height=dp(54), font_size=sp(13),
                       bold=True, background_normal="", background_color=ACCENT_OFF)
        b.bind(on_release=lambda btn, n=name: self.select(n))
        self._tab_buttons[name] = b
        return b

    # ------------------------------------------------------------- tab switch
    def select(self, name):
        self.active = name
        for n, b in self._tab_buttons.items():
            b.background_color = ACCENT if n == name else ACCENT_OFF
        self.content.clear_widgets()
        if name == "Network":
            self.network_scatter.transform = Matrix()  # reset zoom/pan
            self.network.set_brain(self.sim.squid.brain)
            self.content.add_widget(self.network_scatter)
        elif name == "Memory":
            self.content.add_widget(self.memory_cards)
            self.memory_cards.refresh()
        elif name == "Learning":
            self.content.add_widget(self.learning_cards)
            self.learning_cards.refresh()
        elif name == "Decisions":
            self.content.add_widget(self.decisions_panel)
            self.decisions_panel.refresh()
        else:
            self.content.add_widget(self.textpanel)
            self._refresh_text(force=True)

    # ------------------------------------------------------------- refresh
    def refresh(self):
        """Called each tick while the brain screen is visible."""
        if self.active == "Network":
            self.network.set_brain(self.sim.squid.brain)
            return
        now = time.time()
        if now - self._last_text_refresh < self.TEXT_REFRESH:
            return
        self._last_text_refresh = now
        if self.active == "Memory":
            self.memory_cards.refresh()
        elif self.active == "Learning":
            self.learning_cards.refresh()
        elif self.active == "Decisions":
            self.decisions_panel.refresh()
        else:
            self._refresh_text()

    def _refresh_text(self, force=False):
        self._last_text_refresh = time.time()
        builder = {
            "Personality": self._personality_text,
            "Stats": self._stats_text,
            "About": self._about_text,
        }.get(self.active)
        if builder:
            self.textpanel.set_text(builder())

    # ------------------------------------------------------------- tab bodies
    def _h(self, title):
        return f"[b][color=b39ddb]{title}[/color][/b]\n"


    def _personality_text(self):
        s = self.sim.squid
        p = s.personality
        out = [self._h(f"Personality: {p.value.capitalize()}")]
        out.append(describe(p) + "\n")
        stat = PERSONALITY_STAT_MODIFIERS.get(p, {})
        learn = PERSONALITY_LEARNING_MODIFIERS.get(p, {})
        out.append(self._h("Need / mood biases"))
        if stat:
            for k, v in stat.items():
                out.append(f"  {k}: [b]{v}[/b]")
        else:
            out.append("[color=888888]  balanced — no special biases[/color]")
        out.append("\n" + self._h("Learning biases"))
        if learn:
            for k, v in learn.items():
                out.append(f"  {k}: [b]{v}[/b]")
        else:
            out.append("[color=888888]  standard learning[/color]")
        return "\n".join(out)

    def _stats_text(self):
        s = self.sim.squid
        b = s.brain
        conns = sum(1 for (x, y) in b.weights if x < y)
        out = [self._h("Lifetime statistics")]
        # The same labelled figures the desktop Statistics tab shows.
        for label, value in self.sim.stats.display_items():
            out.append(f"{label}: [b]{value}[/b]")
        out.append("")
        out.append(self._h("Brain"))
        out.append(f"Connections: [b]{conns}[/b]   "
                   f"STDP strengthenings: [b]{b.stdp_potentiations}[/b]")
        out.append(f"Memories: [b]{len(s.memory.short_term)}[/b] short-term, "
                   f"[b]{len(s.memory.long_term)}[/b] long-term")
        return "\n".join(out)

    def _about_text(self):
        out = [self._h("Dosidicus brain — STRINg engine")]
        out.append("A tiny, fully visible neural network you raise like a pet. "
                   "It starts with 8 neurons and rewires itself from experience.\n")
        out.append(self._h("Reading the Network tab"))
        out.append("[color=aaddff][b]O[/b][/color]  core stat neuron (hunger, mood, ...)")
        out.append("[color=6fa8dc][b]O[/b][/color]  blue ring = input sensor (what it perceives)")
        out.append("[color=ffd54f][b]O[/b][/color]  gold ring = neuron grown by neurogenesis")
        out.append("Circle brightness = how strongly the neuron is firing.\n")
        out.append("[color=88ff88][b]---[/b][/color] green line = excitatory connection")
        out.append("[color=ff8888][b]---[/b][/color] red line = inhibitory connection")
        out.append("Line thickness = connection strength (learned weight).\n")
        out.append(self._h("How it learns"))
        out.append("Hebbian learning strengthens links between neurons that fire "
                   "together, and STDP adds spike-timing plasticity (neurons that "
                   "fire in quick succession wire up). Sustained novelty, reward or "
                   "stress grows entirely new neurons, and lived events are stored "
                   "as memories that colour future decisions. No two brains develop "
                   "the same way.")
        return "\n".join(out)
