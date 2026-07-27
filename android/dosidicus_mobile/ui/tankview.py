"""TankView - the aquarium: the squid, falling food and poop.

Renders the simulation's world state onto a Kivy canvas each frame. Sprite
frames reuse the original desktop artwork (right/left/sleep swim frames). Tapping
the tank drops food at the touch point.
"""

import os
import time

from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp

from .assets import asset


def _load(name):
    path = asset(name)
    if os.path.exists(path):
        try:
            return CoreImage(path).texture
        except Exception:
            return None
    return None


class TankView(Widget):
    def __init__(self, simulation=None, on_drop_food=None, **kwargs):
        super().__init__(**kwargs)
        self.sim = simulation
        self.on_drop_food = on_drop_food
        self._tex = {
            "right": [_load("right1.png"), _load("right2.png")],
            "left": [_load("left1.png"), _load("left2.png")],
            "sleep": [_load("sleep1.png"), _load("sleep2.png")],
            "sushi": _load("sushi.png"),
            "cheese": _load("cheese.png"),
            "food": _load("food.png"),
            "poop": _load("poop1.png"),
            "sick": _load("sick.png"),
            "love": _load("love.png"),
        }
        self.bind(pos=lambda *a: self.redraw(), size=lambda *a: self.redraw())

    def set_simulation(self, sim):
        self.sim = sim
        self.redraw()

    def _map(self, tx, ty):
        """Map tank coords to widget coords (tank y grows downward)."""
        tw, th = self.sim.tank_size
        x = self.x + (tx / tw) * self.width
        y = self.y + (1.0 - ty / th) * self.height
        return x, y

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self.sim and self.on_drop_food:
            tw, th = self.sim.tank_size
            tx = (touch.x - self.x) / self.width * tw
            self.on_drop_food(tx, 20)
            return True
        return super().on_touch_down(touch)

    def redraw(self, *args):
        self.canvas.clear()
        if not self.sim:
            return
        sim = self.sim
        squid = sim.squid
        with self.canvas:
            # Water: simple vertical gradient via two bands.
            Color(0.05, 0.20, 0.34, 1)
            Rectangle(pos=self.pos, size=(self.width, self.height))
            Color(0.07, 0.28, 0.45, 1)
            Rectangle(pos=self.pos, size=(self.width, self.height * 0.5))
            # Sandy floor.
            Color(0.55, 0.47, 0.30, 1)
            Rectangle(pos=self.pos, size=(self.width, self.height * 0.06))

            # Sizes are proportional to the tank height (with DPI floors) so the
            # squid and food read at a comfortable size on any screen density.
            sq = max(dp(96), self.height * 0.26)
            food_sz = max(dp(30), self.height * 0.08)
            poop_sz = max(dp(22), self.height * 0.055)
            icon_sz = sq * 0.38

            # Poop.
            for p in sim.poop_items:
                px, py = self._map(p["x"], p["y"])
                tex = self._tex["poop"]
                Color(1, 1, 1, 1)
                if tex:
                    Rectangle(texture=tex, pos=(px - poop_sz / 2, py - poop_sz / 2),
                              size=(poop_sz, poop_sz))
                else:
                    Color(0.4, 0.25, 0.1, 1)
                    Rectangle(pos=(px - poop_sz / 3, py - poop_sz / 3),
                              size=(poop_sz * 0.66, poop_sz * 0.66))

            # Food.
            for f in sim.food_items:
                fx, fy = self._map(f["x"], f["y"])
                tex = self._tex.get(f.get("type"), self._tex["sushi"]) or self._tex["food"]
                Color(1, 1, 1, 1)
                if tex:
                    Rectangle(texture=tex, pos=(fx - food_sz / 2, fy - food_sz / 2),
                              size=(food_sz, food_sz))
                else:
                    Color(1.0, 0.6, 0.2, 1)
                    Rectangle(pos=(fx - food_sz / 3, fy - food_sz / 3),
                              size=(food_sz * 0.66, food_sz * 0.66))

            # Squid sprite.
            sx, sy = self._map(squid.x, squid.y)
            frame = int(time.time() * 3) % 2
            if squid.is_sleeping:
                tex = self._tex["sleep"][frame]
            else:
                tex = self._tex[squid.direction][frame]
            Color(1, 1, 1, 1)
            if tex:
                Rectangle(texture=tex, pos=(sx - sq / 2, sy - sq / 2), size=(sq, sq))
            else:
                Color(0.9, 0.5, 0.8, 1)
                Rectangle(pos=(sx - sq / 3, sy - sq / 3), size=(sq * 0.66, sq * 0.66))

            # Status overlays.
            if squid.is_sick and self._tex["sick"]:
                Color(1, 1, 1, 1)
                Rectangle(texture=self._tex["sick"],
                          pos=(sx - icon_sz / 2, sy + sq / 2 - icon_sz * 0.2),
                          size=(icon_sz, icon_sz))
            elif squid.status in ("playing happily", "frolicking") and self._tex["love"]:
                Color(1, 1, 1, 1)
                Rectangle(texture=self._tex["love"],
                          pos=(sx - icon_sz / 2, sy + sq / 2 - icon_sz * 0.2),
                          size=(icon_sz, icon_sz))
