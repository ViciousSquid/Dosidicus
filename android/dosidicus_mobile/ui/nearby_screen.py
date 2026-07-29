"""The 'Nearby squids' screen: local peer-to-peer visits via Nearby Connections.

Host (be discoverable) or Find nearby players; on connect, both sides swap a
compact squid snapshot and each spawns the other's squid as a guest visitor that
swims around for a couple of minutes. A received squid can also be imported as a
full copy.

Off-device (or a build without Play Services) the transport is unavailable, so
the screen shows why and offers a "Preview a visitor" demo that spawns a guest
from your own squid — handy for seeing the feature without two phones.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.metrics import dp, sp

from ..engine import portability as P
from . import nearby


def open_nearby(app):
    NearbyView(app).open()


def _btn(text, cb, color=(0.2, 0.3, 0.42, 1), h=54):
    b = Button(text=text, font_size=sp(16), size_hint_y=None, height=dp(h),
               background_normal="", background_color=color)
    b.bind(on_release=cb)
    return b


class NearbyView(Popup):
    def __init__(self, app, **kwargs):
        self.app = app
        self.available = nearby.is_available()
        self.mgr = None
        self.peer_names = {}          # endpoint_id -> display name
        self.peer_buttons = {}        # endpoint_id -> Button
        self.pending_bytes = {}       # endpoint_id -> received bytes (for import)
        self.my_name = f"{app.sim.squid.personality.value} squid"

        root = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        super().__init__(title="Nearby squids", content=root, size_hint=(0.94, 0.9),
                         title_size=sp(18), **kwargs)

        self.status = Label(text="", markup=True, size_hint_y=None, height=dp(46),
                            halign="center", valign="middle", font_size=sp(14),
                            color=(0.85, 0.88, 0.94, 1))
        self.status.bind(size=lambda *_: setattr(self.status, "text_size", self.status.size))
        root.add_widget(self.status)

        if self.available:
            self._set_status("Host to be found by a friend, or Find to see nearby squids.")
            row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
            row.add_widget(_btn("Host", lambda *_: self._host(), (0.13, 0.42, 0.18, 1)))
            row.add_widget(_btn("Find", lambda *_: self._find(), (0.15, 0.45, 0.6, 1)))
            root.add_widget(row)
            root.add_widget(Label(text="[b]Nearby players[/b]", markup=True,
                                  size_hint_y=None, height=dp(24), font_size=sp(14)))
            self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
            self._list.bind(minimum_height=self._list.setter("height"))
            scroll = ScrollView()
            scroll.add_widget(self._list)
            root.add_widget(scroll)
        else:
            self._set_status(
                "[b]Local peer-to-peer[/b] needs an on-device build with Google Play "
                "Services (Bluetooth + Wi-Fi). It's unavailable here.\n\n"
                "You can still preview what a visiting squid looks like:")
            root.add_widget(Widget(size_hint_y=1))  # spacer

        root.add_widget(_btn("Preview a visitor", lambda *_: self._preview(),
                             (0.5, 0.28, 0.72, 1)))
        root.add_widget(_btn("Close", lambda *_: self.dismiss(), (0.3, 0.3, 0.34, 1)))

        self.bind(on_dismiss=lambda *_: self._teardown())
        if self.available:
            self._connect_manager()

    # ------------------------------------------------------------- helpers
    def _set_status(self, text):
        self.status.text = text

    def _connect_manager(self):
        nearby.request_permissions()
        self.mgr = getattr(self.app, "_nearby", None) or nearby.NearbyManager()
        self.app._nearby = self.mgr
        self.mgr.handlers = {
            "status": self._on_status,
            "peer_found": self._on_peer_found,
            "peer_lost": self._on_peer_lost,
            "connection_initiated": self._on_connection_initiated,
            "connected": self._on_connected,
            "rejected": lambda eid: self._set_status("Connection declined."),
            "disconnected": self._on_disconnected,
            "bytes": self._on_bytes,
        }

    def _host(self):
        self._set_status("Hosting — waiting for a nearby squid to connect…")
        self.mgr.host(self.my_name)

    def _find(self):
        self._set_status("Looking for nearby squids…")
        self.mgr.find()

    # --------------------------------------------------------- transport events
    def _on_status(self, message):
        self._set_status(f"Status: {message}")

    def _on_peer_found(self, endpoint_id, name):
        self.peer_names[endpoint_id] = name
        if endpoint_id not in self.peer_buttons:
            b = _btn(f"Connect to {name}",
                     lambda *_: self.mgr.request(self.my_name, endpoint_id),
                     (0.2, 0.34, 0.5, 1))
            self.peer_buttons[endpoint_id] = b
            self._list.add_widget(b)

    def _on_peer_lost(self, endpoint_id):
        b = self.peer_buttons.pop(endpoint_id, None)
        if b:
            self._list.remove_widget(b)

    def _on_connection_initiated(self, endpoint_id, name, auth_digits):
        self.peer_names[endpoint_id] = name
        self._set_status(f"Connecting to {name}…")
        self.mgr.accept(endpoint_id)     # auto-accept (both sides must)

    def _on_connected(self, endpoint_id):
        name = self.peer_names.get(endpoint_id, "a friend")
        data = P.snapshot_bytes(self.app.sim)
        if len(data) > P.SNAPSHOT_MAX_BYTES:
            self._set_status("Your squid is too complex to send over this link.")
            return
        self.mgr.send(endpoint_id, data)
        self._set_status(f"Connected to {name} — sent your squid for a visit.")

    def _on_disconnected(self, endpoint_id):
        name = self.peer_names.get(endpoint_id, "a friend")
        self._set_status(f"{name} disconnected.")
        self._on_peer_lost(endpoint_id)

    def _on_bytes(self, endpoint_id, base64_data):
        try:
            data = nearby.NearbyManager.decode(base64_data)
            snap = P.snapshot_dict(data)
        except Exception as e:
            self._set_status(f"Received an unreadable squid ({e}).")
            return
        self.pending_bytes[endpoint_id] = data
        name = self.peer_names.get(endpoint_id, "a friend")
        self.app.sim.add_visitor(snap, name=name)
        self.app._flash(f"[color=b39ddb]{name}'s squid is visiting your tank![/color]",
                        seconds=3.5)
        self._offer_import(name, data)

    # ------------------------------------------------------------- preview/import
    def _preview(self):
        snap = P.snapshot_dict(P.snapshot_bytes(self.app.sim))
        self.app.sim.add_visitor(snap, name="Preview",
                                 seconds=self.app.sim.PREVIEW_SECONDS)
        self.app._flash("[color=b39ddb]A visiting squid appeared! It'll swim around "
                        "(and maybe pinch some food), then leave.[/color]", seconds=3.5)
        self.dismiss()

    def _offer_import(self, name, data):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        box.add_widget(Label(
            text=f"{name}'s squid is visiting.\n\nKeep a full copy? This replaces "
                 f"your current squid (export yours first if you want to keep it).",
            markup=True, halign="center", valign="middle", font_size=sp(15)))
        p = Popup(title="Squid received", content=box, size_hint=(0.88, 0.5),
                  title_size=sp(17))
        row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        row.add_widget(_btn("Just visiting", lambda *_: p.dismiss(), (0.3, 0.3, 0.34, 1)))
        row.add_widget(_btn("Import copy",
                            lambda *_: (p.dismiss(), self._do_import(data)),
                            (0.13, 0.42, 0.18, 1)))
        box.add_widget(row)
        p.open()

    def _do_import(self, data):
        try:
            sim = P.sim_from_snapshot(data, tank_size=self.app.sim.tank_size)
        except Exception as e:
            self.app._flash(f"[color=ff8888]Import failed: {e}[/color]")
            return
        self.app.set_simulation(sim)
        self.app.save_now()
        self.app._flash("[color=88ff88]Imported the visiting squid![/color]")

    def _teardown(self):
        if self.mgr:
            self.mgr.stop()
