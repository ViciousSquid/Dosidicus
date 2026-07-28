"""A multi-step guided tutorial, ported from the desktop and reworded for touch.

Shown as a sequence of cards with Skip / Next (Finish on the last step). It's
offered whenever a new game starts (and on first launch).
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp

# (title, body) — ported from the desktop tutorial_step*_text, adapted for the
# mobile controls (Feed/Clean/Decorations/Brain buttons, drag/pinch, ☰ menu).
STEPS = [
    ("Caring for your squid",
     "A squid has hatched — it's yours to look after!\n\n"
     "• Feed it when it's hungry ([b]Feed[/b])\n"
     "• Clean the tank when it gets dirty ([b]Clean[/b])\n"
     "• Tap anywhere in the tank to drop food\n"
     "• Watch how it behaves to learn its personality"),
    ("The neural network",
     "Tap [b]Brain[/b] to see the squid's neural network on the Network tab.\n\n"
     "Its behaviour is driven by its needs — each circle is a neuron. The "
     "network adapts and learns as the squid lives. Pinch to zoom, drag to pan."),
    ("Neurogenesis — growing new neurons",
     "The squid grows [b]entirely new neurons[/b] in response to strong "
     "experiences: novelty, reward or sustained stress.\n\n"
     "Grown neurons appear with a [color=ffd54f]gold ring[/color]. No two "
     "brains ever develop the same way."),
    ("Learning — Hebbian & STDP",
     "When two neurons fire together, their connection strengthens ([b]Hebbian[/b] "
     "learning); firing in quick succession strengthens it too ([b]STDP[/b]).\n\n"
     "This is how the squid learns associations. Watch it on the [b]Learning[/b] tab."),
    ("Decisions & memory",
     "Each moment the brain weighs the squid's needs and recent [b]memories[/b] "
     "to choose an action.\n\n"
     "The [b]Decisions[/b] tab shows every option scored and which one won; the "
     "[b]Memory[/b] tab shows what it remembers."),
    ("Decorations",
     "Tap [b]Decorations[/b] to add plants, rocks and more.\n\n"
     "• [b]Drag[/b] to move  • [b]Pinch[/b] to resize  • [b]Double-tap[/b] to remove\n\n"
     "Plants soothe anxiety; rocks invite play — the squid may pick a rock up "
     "and throw it!"),
    ("Raising your squid",
     "Keep [b]satisfaction[/b] high and [b]anxiety[/b] low, and your squid will "
     "develop unique traits based on how you raise it.\n\n"
     "Use the [b]☰[/b] menu any time to start a new game or export/share your "
     "squid. Have fun!"),
]


def _btn(text, cb, color, width=None):
    b = Button(text=text, font_size=sp(16), bold=True, background_normal="",
               background_color=color, size_hint_x=(None if width else 1))
    if width:
        b.width = width
    b.bind(on_release=cb)
    return b


class _Tutorial:
    def __init__(self, app):
        self.app = app
        self.i = 0
        self.popup = Popup(title="Tutorial", size_hint=(0.9, 0.72), title_size=sp(17),
                           auto_dismiss=False)
        self._build()

    def _build(self):
        title, body = STEPS[self.i]
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        head = Label(text=f"[b]{title}[/b]", markup=True, size_hint_y=None,
                     height=dp(34), halign="left", valign="middle",
                     font_size=sp(19), color=(1, 0.84, 0.2, 1))
        head.bind(size=lambda *_: setattr(head, "text_size", head.size))
        box.add_widget(head)

        body_lbl = Label(text=body, markup=True, halign="left", valign="top",
                         font_size=sp(15), color=(0.93, 0.95, 0.98, 1))
        body_lbl.bind(size=lambda *_: setattr(body_lbl, "text_size", body_lbl.size))
        box.add_widget(body_lbl)

        footer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54),
                           spacing=dp(8))
        step_lbl = Label(text=f"Step {self.i + 1} of {len(STEPS)}", size_hint_x=None,
                         width=dp(120), halign="left", valign="middle",
                         font_size=sp(13), color=(0.7, 0.72, 0.78, 1))
        step_lbl.bind(size=lambda *_: setattr(step_lbl, "text_size", step_lbl.size))
        footer.add_widget(step_lbl)
        footer.add_widget(_btn("Skip", lambda *_: self.popup.dismiss(), (0.3, 0.3, 0.34, 1)))
        last = self.i == len(STEPS) - 1
        footer.add_widget(_btn("Finish" if last else "Next", self._next,
                               (0.5, 0.28, 0.72, 1)))
        box.add_widget(footer)
        self.popup.content = box

    def _next(self, *a):
        if self.i >= len(STEPS) - 1:
            self.popup.dismiss()
        else:
            self.i += 1
            self._build()

    def show(self):
        self.popup.open()


def start_tutorial(app):
    _Tutorial(app).show()


def prompt_tutorial(app):
    """Offer the tutorial when a new game begins."""
    box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
    box.add_widget(Label(
        text="A new squid has hatched!\n\nWould you like a quick guided tour of "
             "how to care for it and read its brain?",
        markup=True, halign="center", valign="middle", font_size=sp(16)))
    p = Popup(title="Welcome to Dosidicus", content=box, size_hint=(0.88, 0.5),
              title_size=sp(17), auto_dismiss=False)
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54), spacing=dp(8))
    row.add_widget(_btn("Not now", lambda *_: p.dismiss(), (0.3, 0.3, 0.34, 1)))
    row.add_widget(_btn("Start tour", lambda *_: (p.dismiss(), start_tutorial(app)),
                        (0.5, 0.28, 0.72, 1)))
    box.add_widget(row)
    p.open()
