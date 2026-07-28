"""Startup splash screen showing the project title and web address."""

import os

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp

from .assets import asset

PROJECT_URL = "github.com/vicioussquid/dosidicus"


class Splash(FloatLayout):
    def __init__(self, on_done=None, **kwargs):
        super().__init__(**kwargs)
        self.on_done = on_done
        with self.canvas.before:
            Color(0.04, 0.05, 0.09, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)

        icon = asset("icon.png")
        if os.path.exists(icon):
            self.add_widget(Image(source=icon, size_hint=(None, None),
                                  size=(dp(150), dp(150)),
                                  pos_hint={"center_x": 0.5, "center_y": 0.6}))

        self.add_widget(self._lbl("[b]Dosidicus electronicus[/b]", sp(26),
                                  (1.0, 0.84, 0.2, 1), 0.5, 0.4))
        self.add_widget(self._lbl("Raise a neural network as a pet", sp(15),
                                  (0.8, 0.82, 0.88, 1), 0.5, 0.33))
        self.add_widget(self._lbl(PROJECT_URL, sp(15),
                                  (0.55, 0.7, 0.95, 1), 0.5, 0.12))

    def _lbl(self, text, size, color, cx, cy):
        lbl = Label(text=text, markup=True, font_size=size, color=color,
                    size_hint=(1, None), height=size * 1.6,
                    halign="center", valign="middle",
                    pos_hint={"center_x": cx, "center_y": cy})
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
        return lbl

    def _sync(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def on_touch_down(self, touch):
        self.dismiss()           # tap to skip
        return True

    def dismiss(self, *a):
        if self.parent:
            self.parent.remove_widget(self)
        if self.on_done:
            cb, self.on_done = self.on_done, None
            cb()
