#!/usr/bin/env python3
"""Capture the real Kivy app at phone resolution using an isolated demo save."""
import os
import random
import sys
from pathlib import Path

ANDROID = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANDROID))
os.chdir(ANDROID)
os.environ.setdefault('KIVY_NO_ARGS', '1')
from kivy.config import Config
Config.set('graphics', 'width', '480')
Config.set('graphics', 'height', '960')
Config.set('graphics', 'resizable', '0')
from kivy.clock import Clock
from kivy.core.window import Window
from dosidicus_mobile.ui.app import DosidicusApp
from dosidicus_mobile.engine import Simulation, Squid, Personality
from dosidicus_mobile.ui.brain_editor import open_brain_editor
from dosidicus_mobile.ui.menu import open_menu, _customise_squid

OUTPUT = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/dosidicus-gallery').resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)


class GalleryApp(DosidicusApp):
    @property
    def user_data_dir(self):
        folder = OUTPUT / 'demo-state'
        folder.mkdir(exist_ok=True)
        return str(folder)

    def _load_or_new(self):
        self._is_first_launch = False
        random.seed(31)
        sim = Simulation(squid=Squid(Personality.ADVENTUROUS))
        sim.squid.name = 'Coral'
        sim.squid.color_tint = (.9, .58, .42)
        sim.add_decoration('plant03.png', 'plant', 160, 400)
        sim.add_decoration('rock01.png', 'rock', 690, 440)
        sim.drop_food(x=450, y=250)
        for _ in range(45):
            sim.update(1)
        return sim

    def on_start(self):
        self.steps = iter([
            ('01-tank', None), ('02-network', 'Network'),
            ('03-learning', 'Learning'), ('04-decisions', 'Decisions'),
            ('05-knowledge', 'Knowledge'), ('06-growth', 'Growth'),
            ('07-brain-designer', 'designer'), ('08-menu', 'menu'),
            ('09-name-colour', 'identity'),
        ])
        Clock.schedule_once(self.next_view, 1)

    def next_view(self, dt):
        try:
            self.capture_name, view = next(self.steps)
        except StopIteration:
            self.stop()
            return
        if getattr(self, 'popup', None):
            self.popup.dismiss(); self.popup = None
        if view == 'identity':
            self.popup = _customise_squid(self)
        elif view in ('designer', 'menu'):
            self.popup = open_brain_editor(self) if view == 'designer' else open_menu(self)
        elif view:
            if not self.showing_brain:
                self._toggle_view()
            self.brain.select(view)
        Clock.schedule_once(self.capture, .5)

    def capture(self, dt):
        self.brain.refresh()
        saved = Window.screenshot(name=str(OUTPUT / (self.capture_name + '.png')))
        Path(saved).replace(OUTPUT / (self.capture_name + '.png'))
        Clock.schedule_once(self.next_view, .2)


GalleryApp().run()
