"""TankView - the aquarium: the squid, falling food and poop.

Renders the simulation's world state onto a Kivy canvas each frame. Sprite
frames reuse the original desktop artwork (right/left/sleep swim frames). Tapping
the tank drops food at the touch point.
"""

import os
import time

from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp

from .assets import asset


SQUID_ASPECT = 253.0 / 147.0  # native sprite aspect (wider than tall)


def _load(name):
    path = asset(name)
    if os.path.exists(path):
        try:
            return CoreImage(path).texture
        except Exception:
            return None
    return None


def _load_egg_frame(rel):
    """Egg anim frames are black-on-white JPGs; key out the white to alpha and
    crop to the egg so it sits nicely on the water."""
    path = asset(rel)
    if not os.path.exists(path):
        return None
    try:
        import numpy as np
        from PIL import Image as PILImage
        from kivy.graphics.texture import Texture
        arr = np.array(PILImage.open(path).convert("RGBA"))
        near_white = arr[:, :, :3].min(axis=2) > 235
        arr[near_white, 3] = 0
        ys, xs = np.where(arr[:, :, 3] > 0)
        if len(xs):
            arr = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        out = PILImage.fromarray(arr)
        tex = Texture.create(size=out.size, colorfmt="rgba")
        tex.blit_buffer(out.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
        tex.flip_vertical()
        return tex
    except Exception:
        return None


def _load_inverted(name):
    """Load an icon with its RGB inverted (black line-art -> white) so it's
    visible against the dark water. Alpha is preserved."""
    path = asset(name)
    if not os.path.exists(path):
        return None
    try:
        from PIL import Image as PILImage, ImageOps
        from kivy.graphics.texture import Texture
        im = PILImage.open(path).convert("RGBA")
        r, g, b, a = im.split()
        inv = ImageOps.invert(PILImage.merge("RGB", (r, g, b)))
        r2, g2, b2 = inv.split()
        out = PILImage.merge("RGBA", (r2, g2, b2, a))
        tex = Texture.create(size=out.size, colorfmt="rgba")
        tex.blit_buffer(out.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
        tex.flip_vertical()
        return tex
    except Exception:
        return _load(name)


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
            # Mental-state icons are black line-art; invert to white so they
            # read against the dark water.
            "sick": _load_inverted("sick.png"),
            "startled": _load_inverted("startled.png"),
            "curious": _load_inverted("curious.png"),
            "ink": _load("inkcloud.png"),
        }
        self._egg_frames = [f for f in
                            (_load_egg_frame(f"egg/anim0{i}.jpg") for i in range(1, 7))
                            if f is not None] or [_load("egg.png")]
        self.bind(pos=lambda *a: self.redraw(), size=lambda *a: self.redraw())

    def set_simulation(self, sim):
        self.sim = sim
        self.redraw()

    @staticmethod
    def _is_curious(squid):
        """Curious mental state: actively investigating, and not asleep."""
        if squid.is_sleeping:
            return False
        s = squid.status.lower()
        if any(k in s for k in ("explor", "curious", "peek", "scout", "seeking",
                                "going for", "eyeing", "investigat", "wander")):
            return True
        return squid.curiosity > 72

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

            # Hatching: show the egg animation (one frame/second) on a lit
            # backdrop, and skip drawing the squid until it emerges.
            if getattr(sim, "hatching", False) and self._egg_frames:
                idx = min(len(self._egg_frames) - 1, int(getattr(sim, "hatch_t", 0)))
                tex = self._egg_frames[idx]
                eh = self.height * 0.42
                ew = eh * (tex.width / tex.height) if tex.height else eh * 0.75
                cx = self.x + self.width * 0.5
                cy = self.y + self.height * 0.52
                Color(0.94, 0.95, 0.90, 0.9)   # soft lit backdrop for contrast
                Ellipse(pos=(cx - ew * 0.7, cy - eh * 0.62), size=(ew * 1.4, eh * 1.24))
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(cx - ew / 2, cy - eh / 2), size=(ew, eh))
                return

            # Sizes are proportional to the tank height (with DPI floors) so the
            # squid and food read at a comfortable size on any screen density.
            # The squid sprite is 253x147, so preserve that aspect (no squish).
            squid_w = max(dp(80), self.height * 0.26) * 0.8   # 20% smaller
            squid_h = squid_w / SQUID_ASPECT
            food_sz = max(dp(22), self.height * 0.06)          # 25% smaller
            poop_sz = max(dp(22), self.height * 0.055)
            icon_sz = squid_h * 0.55

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

            # Squid sprite (aspect-correct; swim frames swap once per second).
            sx, sy = self._map(squid.x, squid.y)
            frame = int(time.time()) % 2
            if squid.is_sleeping:
                tex = self._tex["sleep"][frame]
            else:
                tex = self._tex[squid.direction][frame]
            Color(1, 1, 1, 1)
            if tex:
                Rectangle(texture=tex, pos=(sx - squid_w / 2, sy - squid_h / 2),
                          size=(squid_w, squid_h))
            else:
                Color(0.9, 0.5, 0.8, 1)
                Rectangle(pos=(sx - squid_w / 2, sy - squid_h / 2),
                          size=(squid_w, squid_h))

            # Mental-state icon above the squid, mirroring the desktop set:
            # startled "!" (takes priority — a fright is salient), then sick
            # skull, then curious "?" while it's investigating its world.
            overlay = None
            if getattr(squid, "is_startled", False) and self._tex["startled"]:
                overlay = self._tex["startled"]
            elif squid.is_sick and self._tex["sick"]:
                overlay = self._tex["sick"]
            elif self._is_curious(squid) and self._tex["curious"]:
                overlay = self._tex["curious"]
            if overlay:
                Color(1, 1, 1, 1)
                Rectangle(texture=overlay,
                          pos=(sx - icon_sz / 2, sy + squid_h / 2 - icon_sz * 0.2),
                          size=(icon_sz, icon_sz))

            # Ink clouds (drawn over the squid, fading out with age).
            now = sim.squid.brain.sim_time
            ink_sz = squid_w * 1.9
            for c in sim.ink_clouds:
                age = now - c["t"]
                alpha = max(0.0, 1.0 - age / c.get("ttl", 3.0))
                ix, iy = self._map(c["x"], c["y"])
                if self._tex["ink"]:
                    Color(1, 1, 1, alpha)
                    Rectangle(texture=self._tex["ink"],
                              pos=(ix - ink_sz / 2, iy - ink_sz / 2), size=(ink_sz, ink_sz))
                else:
                    Color(0.05, 0.05, 0.1, alpha * 0.8)
                    Rectangle(pos=(ix - ink_sz / 2, iy - ink_sz / 2), size=(ink_sz, ink_sz))

            # Cleaning sweep: a thick bar travelling right->left over the tank.
            sweep_x = getattr(sim, "sweep_x", None)
            if sweep_x is not None:
                lx, _ = self._map(sweep_x, 0)
                bw = dp(14)
                Color(0.6, 0.9, 1.0, 0.35)
                Rectangle(pos=(lx, self.y), size=(self.width - (lx - self.x), self.height))
                Color(0.75, 0.95, 1.0, 0.9)
                Rectangle(pos=(lx - bw / 2, self.y), size=(bw, self.height))
