"""DosidicusApp - the Kivy application shell.

Portrait, touch-first layout:

    +---------------------------------------+
    | personality  |  age  |  live status   |   header
    +---------------------------------------+
    |                                       |
    |      TANK  view   <-toggle->  BRAIN   |   main viewport
    |                                       |
    +---------------------------------------+
    |  seven live stat bars                 |
    +---------------------------------------+
    | Feed | Clean | Play | Sleep | Brain   |   care bar
    +---------------------------------------+

The App owns the Simulation, drives it from Kivy's Clock, and autosaves to the
platform's writable user-data directory so a squid's cognitive history persists
between launches.
"""

import os
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window

from ..engine import Simulation, Squid, Personality
from .tankview import TankView
from .brainview import BrainView
from .stats import StatsPanel

TANK_SIZE = (900, 500)
AUTOSAVE_EVERY = 20.0  # seconds


class DosidicusApp(App):
    title = "Dosidicus"

    def build(self):
        Window.clearcolor = (0.04, 0.05, 0.08, 1)
        self.save_path = os.path.join(self.user_data_dir, "squid_save.json")
        self.sim = self._load_or_new()
        self._since_save = 0.0
        self._banner_until = 0.0

        root = BoxLayout(orientation="vertical", spacing=2, padding=2)

        # --- Header ---
        self.header = Label(
            text=self._header_text(), markup=True, size_hint_y=None, height=44,
            halign="center", valign="middle")
        self.header.bind(size=lambda *a: setattr(self.header, "text_size", self.header.size))
        root.add_widget(self.header)

        # --- Main viewport (tank + brain stacked, one shown at a time) ---
        self.viewport = FloatLayout(size_hint_y=1)
        self.tank = TankView(self.sim, on_drop_food=self._drop_food,
                             size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.brain = BrainView(self.sim.squid.brain,
                              size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.viewport.add_widget(self.tank)
        self.viewport.add_widget(self.brain)
        self.showing_brain = False
        self.brain.opacity = 0
        self.brain.disabled = True
        root.add_widget(self.viewport)

        # transient banner (neurogenesis etc.)
        self.banner = Label(text="", markup=True, size_hint_y=None, height=0,
                            halign="center", valign="middle", color=(1, 0.85, 0.1, 1))
        root.add_widget(self.banner)

        # --- Stats ---
        self.stats = StatsPanel(self.sim.squid, size_hint_y=None, height=176)
        root.add_widget(self.stats)

        # --- Care bar ---
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=64, spacing=3)
        for label, cb in [
            ("Feed", self._feed), ("Clean", self._clean),
            ("Play", self._play), ("Sleep", self._sleep),
        ]:
            b = Button(text=label, font_size=16, bold=True,
                       background_color=(0.15, 0.45, 0.6, 1))
            b.bind(on_release=cb)
            bar.add_widget(b)
        self.toggle_btn = Button(text="Brain", font_size=16, bold=True,
                                 background_color=(0.5, 0.3, 0.6, 1))
        self.toggle_btn.bind(on_release=self._toggle_view)
        bar.add_widget(self.toggle_btn)
        root.add_widget(bar)

        Clock.schedule_interval(self.tick, 1.0 / 30.0)
        return root

    # ---------------------------------------------------------- persistence
    def _load_or_new(self):
        if os.path.exists(self.save_path):
            try:
                sim = Simulation.load(self.save_path)
                sim.tank_size = TANK_SIZE
                sim.squid.tank_size = TANK_SIZE
                return sim
            except Exception as e:
                print(f"[Dosidicus] Failed to load save ({e}); hatching a new squid.")
        return Simulation(tank_size=TANK_SIZE, squid=Squid(tank_size=TANK_SIZE))

    def _save(self):
        try:
            self.sim.save(self.save_path)
        except Exception as e:
            print(f"[Dosidicus] Save failed: {e}")

    # --------------------------------------------------------------- header
    def _header_text(self):
        s = self.sim.squid
        age = int(s.age_seconds)
        if age < 3600:
            age_str = f"{age // 60}m {age % 60}s"
        else:
            age_str = f"{age // 3600}h {(age % 3600) // 60}m"
        neurons = len(s.brain.neuron_names)
        return (f"[b]{s.personality.value.capitalize()}[/b] squid   "
                f"age [b]{age_str}[/b]   [color=aaddff]{neurons} neurons[/color]\n"
                f"[i]{self.sim.last_status}[/i]")

    # ----------------------------------------------------------- care hooks
    def _drop_food(self, x=None, y=None):
        self.sim.drop_food(x, y, food_type="sushi")

    def _feed(self, *a):
        self.sim.drop_food(food_type="sushi")
        self._flash("[color=88ff88]Dropped food![/color]")

    def _clean(self, *a):
        self.sim.clean_tank()

    def _play(self, *a):
        self.sim.squid.play()

    def _sleep(self, *a):
        self.sim.squid.toggle_sleep()

    def _toggle_view(self, *a):
        self.showing_brain = not self.showing_brain
        self.brain.opacity = 1 if self.showing_brain else 0
        self.brain.disabled = not self.showing_brain
        self.tank.opacity = 0 if self.showing_brain else 1
        self.tank.disabled = self.showing_brain
        self.toggle_btn.text = "Tank" if self.showing_brain else "Brain"

    def _flash(self, msg, seconds=2.5):
        self.banner.text = msg
        self.banner.height = 24
        self._banner_until = time.time() + seconds

    # ------------------------------------------------------------- main loop
    def tick(self, dt):
        dt = min(dt, 0.1)  # clamp after backgrounding so needs don't jump
        status = self.sim.update(dt)
        if self.sim.newborn_neuron:
            kind = self.sim.newborn_neuron.rsplit("_", 1)[0]
            self._flash(f"[b]Neurogenesis![/b] grew a '{kind}' neuron")

        # Redraw only the visible view for efficiency.
        if self.showing_brain:
            self.brain.set_brain(self.sim.squid.brain)
        else:
            self.tank.redraw()
        self.stats.redraw()
        self.header.text = self._header_text()

        if time.time() > self._banner_until and self.banner.height:
            self.banner.text = ""
            self.banner.height = 0

        self._since_save += dt
        if self._since_save >= AUTOSAVE_EVERY:
            self._since_save = 0.0
            self._save()

    # ------------------------------------------------------- lifecycle hooks
    def on_pause(self):
        self._save()
        return True  # keep state so we resume the same squid

    def on_resume(self):
        pass

    def on_stop(self):
        self._save()
