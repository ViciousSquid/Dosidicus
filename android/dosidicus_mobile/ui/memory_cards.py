"""Memory tab rendered as colored cards, like the desktop memory tab.

Each memory is a rounded card whose colour encodes its valence:
  * neurogenesis  -> blue   (a structural milestone)
  * positive      -> green  (mood/reward went up)
  * negative      -> pink   (distress / mood down)
  * neutral       -> yellow
Short-term (active) memories are shown first, then promoted long-term memories.
"""

import os

from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp

from .assets import asset, ASSET_DIR

# card palette (bg r,g,b ; fg r,g,b)
_BLUE = ((0.25, 0.41, 0.88), (1, 1, 1))
_GREEN = ((0.82, 1.0, 0.82), (0.05, 0.2, 0.05))
_PINK = ((1.0, 0.82, 0.86), (0.25, 0.05, 0.1))
_YELLOW = ((1.0, 0.98, 0.80), (0.2, 0.18, 0.05))

# Representative decoration thumbnail per category.
_DECO_ICON = {"plant": "decoration/plant03.png", "rock": "decoration/rock01.png",
              "castle": "decoration/castle.png", "urchin": "decoration/urchin.png"}


def _icon_for(category, key):
    """Resolve a small thumbnail asset for a memory, like the desktop cards."""
    if category == "food":
        cand = f"{key}.png"
        return cand if os.path.exists(asset(cand)) else "food.png"
    if category == "care":
        return "icons/clean.png"
    if category == "play":
        return "love.png"
    if category == "neurogenesis":
        return "ng.png"
    if category == "mental_state":
        return "startled.png"
    if category == "decoration":
        return _DECO_ICON.get(key, "decoration/urchin.png")
    return None


def _valence(category, raw_value):
    if category == "neurogenesis":
        return "neurogenesis", _BLUE
    if isinstance(raw_value, dict):
        good = (raw_value.get("satisfaction", 0) + raw_value.get("happiness", 0)
                + raw_value.get("curiosity", 0) + raw_value.get("cleanliness", 0))
        bad = raw_value.get("anxiety", 0) - min(0, raw_value.get("happiness", 0))
        score = good - bad
        if score > 0:
            return "positive", _GREEN
        if score < 0:
            return "negative", _PINK
    return "neutral", _YELLOW


class _Card(BoxLayout):
    def __init__(self, text, bg, fg, icon=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         padding=(dp(8), dp(8)), spacing=dp(8), **kwargs)
        with self.canvas.before:
            Color(*bg)
            self._rect = RoundedRectangle(radius=[dp(8)])
        self.bind(pos=self._sync, size=self._sync)

        if icon:
            self.add_widget(self._icon_chip(icon))

        lbl = Label(text=text, markup=True, color=(fg[0], fg[1], fg[2], 1),
                    size_hint_y=None, halign="left", valign="middle", font_size=sp(14))
        lbl.bind(width=lambda *_: setattr(lbl, "text_size", (lbl.width, None)),
                 texture_size=self._on_text)
        self._lbl = lbl
        self.add_widget(lbl)

    def _icon_chip(self, icon):
        # A small white plate keeps every thumbnail legible on any card colour.
        chip = AnchorLayout(size_hint=(None, 1), width=dp(48))
        with chip.canvas.before:
            Color(1, 1, 1, 0.92)
            plate = RoundedRectangle(radius=[dp(8)])

        def _pl(*a):
            s = dp(40)
            plate.size = (s, s)
            plate.pos = (chip.center_x - s / 2, chip.center_y - s / 2)
        chip.bind(pos=_pl, size=_pl)
        chip.add_widget(Image(source=asset(icon), size_hint=(None, None),
                              size=(dp(34), dp(34)), allow_stretch=True,
                              keep_ratio=True))
        return chip

    def _on_text(self, lbl, _ts):
        lbl.height = lbl.texture_size[1]
        self.height = max(dp(56), lbl.texture_size[1] + dp(16))

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


class MemoryCards(ScrollView):
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.sim = simulation
        self.box = BoxLayout(orientation="vertical", size_hint_y=None,
                             spacing=dp(6), padding=dp(8))
        self.box.bind(minimum_height=self.box.setter("height"))
        self.add_widget(self.box)

    def _section(self, text):
        lbl = Label(text=f"[b]{text}[/b]", markup=True, size_hint_y=None,
                    height=dp(26), halign="left", valign="middle",
                    color=(0.7, 0.62, 0.85, 1), font_size=sp(14))
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
        return lbl

    def _hint(self, text):
        lbl = Label(text=text, size_hint_y=None, height=dp(30), halign="left",
                    valign="middle", color=(0.6, 0.6, 0.65, 1), font_size=sp(13))
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
        return lbl

    def _card(self, mem, longterm=False):
        cat = mem.get("category")
        label, (bg, fg) = _valence(cat, mem.get("raw_value"))
        value = mem.get("formatted_value") or mem.get("key") or "memory"
        badge = {"neurogenesis": "Neurogenesis", "positive": "Positive",
                 "negative": "Negative", "neutral": "Neutral"}[label]
        extra = ""
        if not longterm:
            imp = mem.get("importance")
            if imp:
                extra = f"   [i]importance {imp:.1f}[/i]"
        text = (f"[b]{mem.get('time_str', '')}[/b]  {value}\n"
                f"[size=12sp]{badge} · {cat}{extra}[/size]")
        return _Card(text, bg, fg, icon=_icon_for(cat, mem.get("key")))

    def refresh(self):
        self.box.clear_widgets()
        mem = self.sim.squid.memory
        now = self.sim.squid.brain.sim_time
        short = mem.get_active_memories_data(now)
        longm = mem.get_long_term_data()

        self.box.add_widget(self._section(f"Short-term memory ({len(short)})"))
        if not short:
            self.box.add_widget(self._hint("No active memories yet — interact with "
                                           "your squid to form some."))
        for m in short:
            self.box.add_widget(self._card(m))

        self.box.add_widget(self._section(f"Long-term memory ({len(longm)})"))
        if not longm:
            self.box.add_widget(self._hint("Important or repeated memories are "
                                           "promoted here over time."))
        for m in longm[:25]:
            self.box.add_widget(self._card(m, longterm=True))
