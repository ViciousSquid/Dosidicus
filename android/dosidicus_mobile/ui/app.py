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
    | Feed | Clean | Play | Brain/Tank      |   care bar
    +---------------------------------------+

The Brain view is itself a tabbed inspector (Network / Learning / Memory /
Decisions / Personality / Stats / About). The squid sleeps on its own when
tired, so there is no manual sleep button.

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
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp

from ..engine import Simulation, Squid, Personality
from .tankview import TankView
from .brain_screen import BrainScreen
from .stats import StatsPanel
from .decorations import DecorationLayer, open_decoration_palette
from .menu import open_menu
from .tutorial import prompt_tutorial
from .splash import Splash

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

        # --- Header: hamburger menu + status line ---
        topbar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52))
        self.menu_btn = Button(size_hint_x=None, width=dp(52), background_normal="",
                               background_color=(0.2, 0.22, 0.3, 1))
        self.menu_btn.bind(on_release=lambda *_: open_menu(self))
        with self.menu_btn.canvas.after:
            Color(0.9, 0.92, 0.96, 1)
            self._burger = [Rectangle(), Rectangle(), Rectangle()]
        self.menu_btn.bind(pos=self._draw_burger, size=self._draw_burger)
        topbar.add_widget(self.menu_btn)
        self.header = Label(
            text=self._header_text(), markup=True, size_hint_x=1,
            halign="center", valign="middle", font_size=sp(16))
        self.header.bind(size=lambda *a: setattr(self.header, "text_size", self.header.size))
        topbar.add_widget(self.header)
        root.add_widget(topbar)

        # --- Main viewport (tank + decorations + brain, one "view" shown) ---
        self.viewport = FloatLayout(size_hint_y=1)
        self.tank = TankView(self.sim, on_drop_food=self._drop_food,
                             size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        # Decoration layer sits over the tank so decorations can be dragged/pinched.
        self.deco_layer = DecorationLayer(self.sim, size_hint=(1, 1),
                                          pos_hint={"x": 0, "y": 0})
        self.brain = BrainScreen(self.sim,
                                 size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        # Only the active view is kept in the tree. A hidden-but-present widget
        # would still swallow touches (a disabled Kivy widget consumes touches
        # that land on it), which previously blocked dragging decorations.
        self.showing_brain = False
        self.viewport.add_widget(self.tank)
        self.viewport.add_widget(self.deco_layer)  # decoration overlay on top
        root.add_widget(self.viewport)

        # transient banner (neurogenesis etc.)
        self.banner = Label(text="", markup=True, size_hint_y=None, height=0,
                            halign="center", valign="middle", font_size=sp(15),
                            color=(1, 0.85, 0.1, 1))
        root.add_widget(self.banner)

        # --- Stats ---
        self.stats = StatsPanel(self.sim.squid, size_hint_y=None, height=dp(196))
        root.add_widget(self.stats)

        # --- Care bar ---
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(72),
                        spacing=dp(3))
        TEAL = (0.15, 0.45, 0.6, 1)
        DARK_GREEN = (0.13, 0.42, 0.18, 1)
        for label, cb, color in [
            ("Feed", self._feed, TEAL),
            ("Clean", self._clean, TEAL),
            ("Decorations", self._decorations, DARK_GREEN),
        ]:
            b = Button(text=label, font_size=sp(17), bold=True,
                       background_normal="", background_color=color)
            b.bind(on_release=cb)
            bar.add_widget(b)
        self.toggle_btn = Button(text="Brain", font_size=sp(17), bold=True,
                                 background_normal="", background_color=(0.5, 0.28, 0.72, 1))
        self.toggle_btn.bind(on_release=self._toggle_view)
        bar.add_widget(self.toggle_btn)
        root.add_widget(bar)

        Clock.schedule_interval(self.tick, 1.0 / 30.0)

        # First launch (no save): begin as an egg and offer the tutorial once
        # it hatches (handled in tick()).
        self._pending_tutorial = False
        self._was_hatching = False
        if getattr(self, "_is_first_launch", False):
            self.sim.start_hatching()
            self._pending_tutorial = True
            self._was_hatching = True

        # Startup splash (title + project URL) over the game, auto-dismissed.
        container = FloatLayout()
        container.add_widget(root)
        self._splash = Splash()
        container.add_widget(self._splash)
        Clock.schedule_once(lambda dt: self._splash.dismiss(), 2.6)
        return container

    # ---------------------------------------------------------- persistence
    def _load_or_new(self):
        if os.path.exists(self.save_path):
            try:
                sim = Simulation.load(self.save_path)
                sim.tank_size = TANK_SIZE
                sim.squid.tank_size = TANK_SIZE
                self._is_first_launch = False
                return sim
            except Exception as e:
                print(f"[Dosidicus] Failed to load save ({e}); hatching a new squid.")
        self._is_first_launch = True  # no save yet -> offer the tutorial
        return Simulation(tank_size=TANK_SIZE, squid=Squid(tank_size=TANK_SIZE))

    def _save(self):
        try:
            self.sim.save(self.save_path)
        except Exception as e:
            print(f"[Dosidicus] Save failed: {e}")

    def save_now(self):
        self._save()

    def _draw_burger(self, *a):
        b = self.menu_btn
        bw, bh, gap = dp(24), dp(3), dp(7)
        for i, rect in enumerate(self._burger):
            rect.size = (bw, bh)
            rect.pos = (b.center_x - bw / 2, b.center_y + gap - i * gap - bh / 2)

    # ------------------------------------------------------- swap the squid
    def set_simulation(self, sim):
        """Point every view at a new Simulation (import / new game)."""
        self.sim = sim
        sim.tank_size = TANK_SIZE
        sim.squid.tank_size = TANK_SIZE
        self.tank.set_simulation(sim)
        self.deco_layer.set_simulation(sim)
        self.brain.set_simulation(sim)
        self.stats.set_squid(sim.squid)
        if self.showing_brain:
            self._toggle_view()  # drop back to the tank to see the new squid
        self.tank.redraw()

    def new_game(self):
        self.set_simulation(Simulation(tank_size=TANK_SIZE, squid=Squid(tank_size=TANK_SIZE)))
        self.sim.start_hatching()            # a new game begins as an egg
        self._pending_tutorial = True         # offer the tutorial once it hatches
        self._was_hatching = True
        self.save_now()

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

    def _decorations(self, *a):
        # Adding decorations only makes sense over the tank; switch to it first.
        if self.showing_brain:
            self._toggle_view()
        open_decoration_palette(self._add_decoration)

    def _add_decoration(self, deco_type, category):
        tw, th = self.sim.tank_size
        deco = self.sim.add_decoration(deco_type, category, x=tw * 0.5, y=th * 0.55)
        self.deco_layer.add(deco)
        self._flash("[color=88ff88]Added — drag to move, pinch to resize, "
                    "double-tap to remove.[/color]", seconds=3.5)

    def _toggle_view(self, *a):
        self.showing_brain = not self.showing_brain
        self.viewport.clear_widgets()
        if self.showing_brain:
            self.viewport.add_widget(self.brain)
            self.toggle_btn.text = "Tank"
        else:
            self.viewport.add_widget(self.tank)
            self.viewport.add_widget(self.deco_layer)
            self.deco_layer.rebuild()
            self.toggle_btn.text = "Brain"

    def _flash(self, msg, seconds=2.5):
        self.banner.text = msg
        self.banner.height = 24
        self._banner_until = time.time() + seconds

    # ------------------------------------------------------------- main loop
    def tick(self, dt):
        dt = min(dt, 0.1)  # clamp after backgrounding so needs don't jump
        status = self.sim.update(dt)

        # Egg just hatched: celebrate and (first time) offer the tutorial.
        if self._was_hatching and not self.sim.hatching:
            self._was_hatching = False
            self._flash("[color=b39ddb]Your squid has hatched![/color]", seconds=3.0)
            if self._pending_tutorial:
                self._pending_tutorial = False
                Clock.schedule_once(lambda dt: prompt_tutorial(self), 0.4)

        if self.sim.newborn_neuron:
            kind = self.sim.newborn_neuron.rsplit("_", 1)[0]
            self._flash(f"[b]Neurogenesis![/b] grew a '{kind}' neuron")

        # Redraw only the visible view for efficiency.
        if self.showing_brain:
            self.brain.refresh()
        else:
            self.tank.redraw()
            self.deco_layer.sync_physics()  # move carried/thrown rocks
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
