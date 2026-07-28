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
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.scatterlayout import ScatterLayout
from kivy.graphics import Color, Rectangle
from kivy.graphics.transformation import Matrix
from kivy.core.window import Window
from kivy.metrics import dp, sp

from .brainview import BrainView
from .memory_cards import MemoryCards
from .learning_cards import LearningCards
from .decisions_panel import DecisionsPanel
from .sharing import open_url
from ..engine.personality import (
    describe, PERSONALITY_STAT_MODIFIERS, PERSONALITY_LEARNING_MODIFIERS,
)

TABS = ["Network", "Learning", "Memory", "Decisions", "Personality", "Stats", "About"]

ACCENT = (0.5, 0.3, 0.6, 1)
ACCENT_OFF = (0.22, 0.18, 0.28, 1)

# Squid tint palette cycled by the About-page "Change colour" button. None is
# the squid's natural colour; the rest are gentle washes (r,g,b floats 0-1).
SQUID_TINTS = [
    None,
    (1.0, 0.45, 0.45),   # coral
    (0.45, 0.7, 1.0),    # blue
    (0.55, 1.0, 0.6),    # green
    (1.0, 0.85, 0.35),   # gold
    (0.8, 0.55, 1.0),    # violet
    (1.0, 0.6, 0.9),     # pink
    (0.4, 0.9, 0.9),     # teal
]


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
            on_ref_press=lambda _lbl, ref: open_url(ref),
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
        self._tint_index = 0
        self.about_panel = self._build_about_panel()

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
        tint = getattr(sim.squid, "color_tint", None)
        self._tint_index = (SQUID_TINTS.index(tint)
                            if tint in SQUID_TINTS else 0)
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

    # ---------------------------------------------------- About panel + tint
    def _build_about_panel(self):
        panel = BoxLayout(orientation="vertical")
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(58),
                        spacing=dp(8), padding=(dp(10), dp(6)))
        btn = Button(text="Change colour", font_size=sp(16), bold=True,
                     background_normal="", background_color=(0.5, 0.28, 0.72, 1))
        btn.bind(on_release=lambda *_: self._change_colour())
        bar.add_widget(btn)
        # A swatch showing the current tint.
        self._swatch = Widget(size_hint_x=None, width=dp(58))
        with self._swatch.canvas:
            self._swatch_color = Color(0.5, 0.5, 0.5, 1)
            self._swatch_rect = Rectangle(pos=self._swatch.pos, size=self._swatch.size)
        self._swatch.bind(
            pos=lambda *_: setattr(self._swatch_rect, "pos", self._swatch.pos),
            size=lambda *_: setattr(self._swatch_rect, "size", self._swatch.size))
        bar.add_widget(self._swatch)
        panel.add_widget(bar)
        self.about_scroll = _ScrollText()
        panel.add_widget(self.about_scroll)
        return panel

    def _sync_swatch(self):
        tint = getattr(self.sim.squid, "color_tint", None)
        r, g, b = tint if tint else (0.75, 0.75, 0.75)
        self._swatch_color.rgba = (r, g, b, 1)

    def _change_colour(self):
        """Cycle the squid's tint (mirrors the desktop 'change colour')."""
        self._tint_index = (self._tint_index + 1) % len(SQUID_TINTS)
        self.sim.squid.color_tint = SQUID_TINTS[self._tint_index]
        try:
            self.sim.stats.times_colour_changed += 1
        except AttributeError:
            pass
        self._sync_swatch()

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
        elif name == "About":
            self._sync_swatch()
            self.about_scroll.set_text(self._about_text())
            self.content.add_widget(self.about_panel)
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
        if self.active == "About":
            self.about_scroll.set_text(self._about_text())
            return
        builder = {
            "Personality": self._personality_text,
            "Stats": self._stats_text,
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
                   "the same way.\n")
        out.append(self._h("Project"))
        out.append("[ref=https://github.com/vicioussquid/dosidicus]"
                   "[color=6fa8dc][u]github.com/vicioussquid/dosidicus[/u][/color][/ref]")
        return "\n".join(out)
