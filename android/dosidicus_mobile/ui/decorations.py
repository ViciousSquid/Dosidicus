"""Decoration placement layer + palette.

Decorations are interactive widgets (Kivy ``Scatter``) laid over the tank, which
gives multi-touch **drag to move** and **pinch to resize** for free. Double-tap a
decoration to remove it. Every change is written back to ``Simulation.decorations``
so placement, size and choice all persist in the save file.

The palette is a popup grid of thumbnails; tapping one drops that decoration into
the middle of the tank.
"""

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatter import Scatter
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp

from .assets import asset

# (asset file under assets/decoration/, category used by the brain effects)
DECO_CATALOG = [
    ("plant03.png", "plant"),
    ("plant07.png", "plant"),
    ("plant12.png", "plant"),
    ("Znewplant04.png", "plant"),
    ("rock01.png", "rock"),
    ("rock02.png", "rock"),
    ("bigr02.png", "rock"),
    ("castle.png", "castle"),
    ("urchin.png", "urchin"),
]

_ASPECT_CACHE = {}


def _aspect(deco_type):
    """width/height of a decoration texture (cached)."""
    if deco_type not in _ASPECT_CACHE:
        try:
            tex = CoreImage(asset(f"decoration/{deco_type}")).texture
            _ASPECT_CACHE[deco_type] = (tex.width / tex.height) if tex.height else 1.0
        except Exception:
            _ASPECT_CACHE[deco_type] = 1.0
    return _ASPECT_CACHE[deco_type]


class _DecoScatter(Scatter):
    def __init__(self, layer, deco, **kwargs):
        super().__init__(
            do_rotation=False, do_translation=True, do_scale=True,
            scale_min=0.3, scale_max=3.5, size_hint=(None, None), **kwargs)
        self.layer = layer
        self.deco = deco
        img = Image(source=asset(f"decoration/{deco['type']}"),
                    allow_stretch=True, keep_ratio=True,
                    size=self.size, size_hint=(None, None))
        self.bind(size=lambda *_: setattr(img, "size", self.size))
        self.add_widget(img)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and touch.is_double_tap:
            self.layer.remove(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        handled = super().on_touch_up(touch)
        # After any manipulation, persist the new centre + scale.
        if self.collide_point(*touch.pos) or touch.grab_current is self:
            self.layer.sync(self)
        return handled


class DecorationLayer(FloatLayout):
    """Overlay that owns one _DecoScatter per Simulation decoration."""

    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.sim = simulation
        self._scatters = {}
        self.bind(size=lambda *_: self.rebuild(), pos=lambda *_: self.rebuild())

    # base on-screen height of a decoration at scale 1.0 (responsive, DPI-safe)
    def _base_h(self):
        return max(dp(56), self.height * 0.18)

    # ---- coordinate mapping between tank space and this widget ----
    def _to_screen(self, tx, ty):
        tw, th = self.sim.tank_size
        return (self.x + (tx / tw) * self.width,
                self.y + (1.0 - ty / th) * self.height)

    def _to_tank(self, sx, sy):
        tw, th = self.sim.tank_size
        return ((sx - self.x) / self.width * tw,
                (1.0 - (sy - self.y) / self.height) * th)

    def _place(self, scatter, deco):
        base_h = self._base_h()
        aspect = _aspect(deco["type"])
        scatter.size = (base_h * aspect, base_h)
        scatter.scale = deco.get("scale", 1.0)
        cx, cy = self._to_screen(deco["x"], deco["y"])
        scatter.center = (cx, cy)

    def rebuild(self, *args):
        """Recreate all scatters (on load, resize or orientation change)."""
        self.clear_widgets()
        self._scatters.clear()
        if self.width < 2 or self.height < 2:
            return
        for deco in self.sim.decorations:
            sc = _DecoScatter(self, deco)
            self._place(sc, deco)
            self._scatters[deco["id"]] = sc
            self.add_widget(sc)

    def add(self, deco):
        sc = _DecoScatter(self, deco)
        self._place(sc, deco)
        self._scatters[deco["id"]] = sc
        self.add_widget(sc)

    def remove(self, scatter):
        self.sim.remove_decoration(scatter.deco["id"])
        self._scatters.pop(scatter.deco["id"], None)
        self.remove_widget(scatter)

    def sync(self, scatter):
        """Write a scatter's current centre + scale back to the sim record."""
        tx, ty = self._to_tank(*scatter.center)
        tw, th = self.sim.tank_size
        tx = max(0, min(tw, tx))
        ty = max(0, min(th, ty))
        self.sim.update_decoration(scatter.deco["id"], x=tx, y=ty, scale=scatter.scale)


def open_decoration_palette(on_pick):
    """Show a grid of decoration thumbnails; call on_pick(type, category)."""
    popup = Popup(title="Add a decoration", size_hint=(0.92, 0.8),
                  title_size=dp(18))
    scroll = ScrollView()
    grid = GridLayout(cols=3, spacing=dp(8), padding=dp(8), size_hint_y=None)
    grid.bind(minimum_height=grid.setter("height"))
    cell = dp(110)
    for deco_type, category in DECO_CATALOG:
        btn = Button(size_hint_y=None, height=cell,
                     background_normal=asset(f"decoration/{deco_type}"),
                     background_down=asset(f"decoration/{deco_type}"))

        def _pick(_btn, t=deco_type, c=category):
            popup.dismiss()
            on_pick(t, c)
        btn.bind(on_release=_pick)
        grid.add_widget(btn)
    scroll.add_widget(grid)
    popup.content = scroll
    popup.open()
    return popup
