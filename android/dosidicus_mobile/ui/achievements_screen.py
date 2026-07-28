"""The Achievements window (mobile port of the desktop achievements dialog).

A header with total points + unlock progress, a scrollable row of category
filters, and a scrolling list of cards. Locked (non-hidden) achievements show a
lock and a progress bar; unlocked ones show their icon in the tier colour.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line
from kivy.metrics import dp, sp

from ..engine.achievements import (
    CATEGORY_ORDER, CATEGORY_LABELS, TIER_COLORS, TIER_NAMES,
)


def open_achievements(app):
    AchievementsView(app).open()


class AchievementsView(Popup):
    def __init__(self, app, **kwargs):
        self.app = app
        self.mgr = app.sim.achievements
        self.filter = None
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        super().__init__(title="Achievements", content=root,
                         size_hint=(0.96, 0.94), title_size=sp(18), **kwargs)

        # Header: points + progress.
        pts, unlocked, total, maxpts = self.mgr.summary()
        self.header = Label(
            text=(f"[b][color=ffd700]{pts}[/color][/b] / {maxpts} pts     "
                  f"[b]{unlocked}[/b] / {total} unlocked"),
            markup=True, size_hint_y=None, height=dp(30), font_size=sp(16))
        root.add_widget(self.header)

        # Category filter chips.
        strip = ScrollView(size_hint_y=None, height=dp(42), do_scroll_y=False,
                           bar_width=0)
        self._chips_row = BoxLayout(orientation="horizontal", size_hint_x=None,
                                    spacing=dp(4), padding=(dp(2), dp(2)))
        self._chips_row.bind(minimum_width=self._chips_row.setter("width"))
        self._chips = {}
        self._add_chip("All", None)
        for cat in CATEGORY_ORDER:
            self._add_chip(CATEGORY_LABELS[cat], cat)
        strip.add_widget(self._chips_row)
        root.add_widget(strip)

        # Scrolling card list.
        self._scroll = ScrollView()
        self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6),
                               padding=(dp(2), dp(2)))
        self._list.bind(minimum_height=self._list.setter("height"))
        self._scroll.add_widget(self._list)
        root.add_widget(self._scroll)

        close = Button(text="Close", size_hint_y=None, height=dp(50), font_size=sp(16),
                       bold=True, background_normal="", background_color=(0.3, 0.4, 0.5, 1))
        close.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close)

        self._rebuild()

    def _add_chip(self, label, cat):
        b = Button(text=label, size_hint_x=None, width=dp(96), font_size=sp(13),
                   bold=True, background_normal="", background_color=(0.22, 0.26, 0.34, 1))
        b.bind(on_release=lambda *_: self._set_filter(cat))
        self._chips_row.add_widget(b)
        self._chips[cat] = b

    def _set_filter(self, cat):
        self.filter = cat
        self._rebuild()

    def _rebuild(self):
        for cat, b in self._chips.items():
            b.background_color = ((0.5, 0.28, 0.72, 1) if cat == self.filter
                                  else (0.22, 0.26, 0.34, 1))
        self._list.clear_widgets()
        for item in self.mgr.items(self.filter):
            self._list.add_widget(_Card(item))


class _Card(BoxLayout):
    def __init__(self, item, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(78),
                         spacing=dp(8), padding=(dp(10), dp(6)), **kwargs)
        ach = item["ach"]
        unlocked = item["unlocked"]
        tier_hex = TIER_COLORS.get(ach.tier, "cd7f32")
        r, g, b = (int(tier_hex[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        with self.canvas.before:
            if unlocked:
                Color(r, g, b, 0.22)
            else:
                Color(0.5, 0.5, 0.55, 0.12)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
            Color(r, g, b, 1) if unlocked else Color(0.5, 0.5, 0.55, 0.6)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
            # inner fill to leave only a border ring
            Color(0.09, 0.10, 0.13, 1)
            self._inner = RoundedRectangle(radius=[dp(7)])
        self.bind(pos=self._sync, size=self._sync)

        self.add_widget(_Medal((r, g, b), unlocked, ach.tier))

        info = BoxLayout(orientation="vertical", spacing=dp(2))
        name = Label(text=f"[b]{ach.name}[/b]", markup=True, halign="left",
                     valign="middle", size_hint_y=None, height=dp(22), font_size=sp(15),
                     color=(1, 1, 1, 1) if unlocked else (0.72, 0.74, 0.8, 1))
        name.bind(size=lambda *_: setattr(name, "text_size", name.size))
        info.add_widget(name)
        desc = Label(text=ach.description, halign="left", valign="top", font_size=sp(12),
                     color=(0.82, 0.85, 0.9, 1) if unlocked else (0.6, 0.62, 0.68, 1))
        desc.bind(size=lambda *_: setattr(desc, "text_size", desc.size))
        info.add_widget(desc)
        if ach.target_count > 1 and not unlocked:
            bar = ProgressBar(max=ach.target_count, value=item["progress"],
                              size_hint_y=None, height=dp(10))
            info.add_widget(bar)
            prog = Label(text=f"{item['progress']}/{ach.target_count}", halign="left",
                         valign="middle", size_hint_y=None, height=dp(16), font_size=sp(11),
                         color=(0.7, 0.72, 0.78, 1))
            prog.bind(size=lambda *_: setattr(prog, "text_size", prog.size))
            info.add_widget(prog)
        self.add_widget(info)

        pts = Label(text=f"[b][color={tier_hex}]+{ach.points}[/color][/b]\n"
                         f"[color=888888][size=10sp]{TIER_NAMES.get(ach.tier, '')}[/size][/color]",
                    markup=True, size_hint_x=None, width=dp(64), halign="center",
                    valign="middle", font_size=sp(14))
        pts.bind(size=lambda *_: setattr(pts, "text_size", pts.size))
        self.add_widget(pts)

    def _sync(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.pos = self.pos
        self._border.size = self.size
        self._inner.pos = (self.x + dp(2), self.y + dp(2))
        self._inner.size = (self.width - dp(4), self.height - dp(4))


class _Medal(Widget):
    """A tier-coloured medal icon (Kivy can't render the desktop's emoji, so we
    draw a coin: a filled disc + ring, a star for unlocked, a padlock locked)."""

    def __init__(self, rgb, unlocked, tier, **kwargs):
        super().__init__(size_hint_x=None, width=dp(52), **kwargs)
        self._rgb = rgb
        self._unlocked = unlocked
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *a):
        self.canvas.clear()
        r, g, b = self._rgb
        cx, cy = self.center_x, self.center_y
        rad = dp(20)
        with self.canvas:
            if self._unlocked:
                Color(r, g, b, 1)
            else:
                Color(0.5, 0.5, 0.55, 0.5)
            Ellipse(pos=(cx - rad, cy - rad), size=(rad * 2, rad * 2))
            Color(0, 0, 0, 0.28)
            Line(circle=(cx, cy, rad), width=dp(1.5))
            if self._unlocked:
                Color(1, 1, 1, 0.95)
                Line(points=self._star(cx, cy, rad * 0.62, rad * 0.26), width=dp(1.4),
                     close=True)
            else:
                # small padlock: shackle arc + body
                Color(0.85, 0.86, 0.9, 0.9)
                Line(circle=(cx, cy + dp(3), dp(5), 180, 360), width=dp(1.4))
                Line(rectangle=(cx - dp(6), cy - dp(8), dp(12), dp(10)), width=dp(1.4))

    @staticmethod
    def _star(cx, cy, outer, inner):
        import math
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = outer if i % 2 == 0 else inner
            pts += [cx + rr * math.cos(ang), cy + rr * math.sin(ang)]
        return pts
