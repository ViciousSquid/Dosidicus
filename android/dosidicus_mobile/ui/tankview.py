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
    SQUID_W = 90
    SQUID_H = 90

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

            # Poop.
            for p in sim.poop_items:
                px, py = self._map(p["x"], p["y"])
                tex = self._tex["poop"]
                Color(1, 1, 1, 1)
                if tex:
                    Rectangle(texture=tex, pos=(px - 12, py - 12), size=(24, 24))
                else:
                    Color(0.4, 0.25, 0.1, 1)
                    Rectangle(pos=(px - 8, py - 8), size=(16, 16))

            # Food.
            for f in sim.food_items:
                fx, fy = self._map(f["x"], f["y"])
                tex = self._tex.get(f.get("type"), self._tex["sushi"]) or self._tex["food"]
                Color(1, 1, 1, 1)
                if tex:
                    Rectangle(texture=tex, pos=(fx - 16, fy - 16), size=(32, 32))
                else:
                    Color(1.0, 0.6, 0.2, 1)
                    Rectangle(pos=(fx - 10, fy - 10), size=(20, 20))

            # Squid sprite.
            sx, sy = self._map(squid.x, squid.y)
            frame = int(time.time() * 3) % 2
            if squid.is_sleeping:
                tex = self._tex["sleep"][frame]
            else:
                tex = self._tex[squid.direction][frame]
            Color(1, 1, 1, 1)
            if tex:
                Rectangle(texture=tex,
                          pos=(sx - self.SQUID_W / 2, sy - self.SQUID_H / 2),
                          size=(self.SQUID_W, self.SQUID_H))
            else:
                Color(0.9, 0.5, 0.8, 1)
                Rectangle(pos=(sx - 30, sy - 30), size=(60, 60))

            # Status overlays.
            if squid.is_sick and self._tex["sick"]:
                Color(1, 1, 1, 1)
                Rectangle(texture=self._tex["sick"],
                          pos=(sx - 12, sy + self.SQUID_H / 2 - 6), size=(28, 28))
            elif squid.status in ("playing happily", "frolicking") and self._tex["love"]:
                Color(1, 1, 1, 1)
                Rectangle(texture=self._tex["love"],
                          pos=(sx - 12, sy + self.SQUID_H / 2 - 6), size=(24, 24))
