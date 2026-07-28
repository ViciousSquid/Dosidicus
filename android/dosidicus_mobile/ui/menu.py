"""Hamburger menu: New game, Export squid, Import squid."""

import os
import time

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.metrics import dp, sp

from ..engine.portability import export_squid, import_squid
from . import sharing


def _btn(text, cb, color=(0.2, 0.3, 0.42, 1)):
    b = Button(text=text, font_size=sp(17), size_hint_y=None, height=dp(56),
               background_normal="", background_color=color)
    b.bind(on_release=cb)
    return b


def _message(title, msg):
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
    lbl = Label(text=msg, markup=True, halign="left", valign="top", font_size=sp(15))
    lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
    box.add_widget(lbl)
    p = Popup(title=title, content=box, size_hint=(0.9, 0.5), title_size=sp(17))
    close = _btn("OK", lambda *_: p.dismiss(), color=(0.3, 0.4, 0.5, 1))
    box.add_widget(close)
    p.open()
    return p


def open_menu(app):
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
    popup = Popup(title="Menu", content=box, size_hint=(0.86, 0.62), title_size=sp(18))

    def close(*_):
        popup.dismiss()

    box.add_widget(_btn("New game", lambda *_: (close(), _confirm_new_game(app)),
                        color=(0.5, 0.28, 0.72, 1)))
    box.add_widget(_btn("Export squid", lambda *_: (close(), _export(app)),
                        color=(0.13, 0.42, 0.18, 1)))
    box.add_widget(_btn("Import squid", lambda *_: (close(), _import(app)),
                        color=(0.15, 0.45, 0.6, 1)))
    box.add_widget(Label(size_hint_y=None, height=dp(4)))
    box.add_widget(_btn("Cancel", close, color=(0.3, 0.3, 0.34, 1)))
    popup.open()
    return popup


# --------------------------------------------------------------- new game
def _confirm_new_game(app):
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
    box.add_widget(Label(
        text="Start a new game?\nYour current squid will be replaced.\n"
             "Export it first if you want to keep it.",
        halign="center", valign="middle", font_size=sp(15)))
    p = Popup(title="New game", content=box, size_hint=(0.86, 0.5), title_size=sp(18))
    row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
    row.add_widget(_btn("Cancel", lambda *_: p.dismiss(), color=(0.3, 0.3, 0.34, 1)))
    row.add_widget(_btn("New squid", lambda *_: (p.dismiss(), app.new_game()),
                        color=(0.5, 0.28, 0.72, 1)))
    box.add_widget(row)
    p.open()


# --------------------------------------------------------------- export
def _export(app):
    try:
        out_dir = sharing.export_dir(app)
        name = f"squid-{app.sim.squid.personality.value}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        path = os.path.join(out_dir, name)
        export_squid(app.sim, path)
    except Exception as e:
        _message("Export failed", f"[color=ff8888]{e}[/color]")
        return
    shared = sharing.share_file(path, title="Share your squid")
    if not shared:
        _message("Squid exported",
                 f"Saved to:\n[b]{path}[/b]\n\nOpen your Files app to share this "
                 f".zip, or import it on another device.")


# --------------------------------------------------------------- import
def _import(app):
    def do_import(path):
        if not path:
            return
        try:
            sim = import_squid(path, tank_size=app.sim.tank_size)
        except Exception as e:
            _message("Import failed", f"[color=ff8888]Couldn't read that squid:\n{e}[/color]")
            return
        app.set_simulation(sim)
        app.save_now()
        _message("Squid imported",
                 f"Loaded [b]{sim.squid.personality.value}[/b] squid "
                 f"with [b]{len(sim.squid.brain.neuron_names)}[/b] neurons.")

    if sharing.pick_file(do_import):
        return  # native/plyer picker launched
    _desktop_chooser(app, do_import)


def _desktop_chooser(app, on_choice):
    start = sharing.export_dir(app)
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
    chooser = FileChooserListView(path=start if os.path.isdir(start) else os.path.expanduser("~"),
                                  filters=["*.zip"])
    box.add_widget(chooser)
    p = Popup(title="Import squid (.zip)", content=box, size_hint=(0.95, 0.9),
              title_size=sp(17))
    row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
    row.add_widget(_btn("Cancel", lambda *_: p.dismiss(), color=(0.3, 0.3, 0.34, 1)))

    def _load(*_):
        sel = chooser.selection[0] if chooser.selection else None
        p.dismiss()
        on_choice(sel)
    row.add_widget(_btn("Import", _load, color=(0.15, 0.45, 0.6, 1)))
    box.add_widget(row)
    p.open()
