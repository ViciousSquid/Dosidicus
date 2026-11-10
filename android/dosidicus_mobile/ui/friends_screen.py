"""The 'Friends' screen: meet a friend's squid over the internet.

The phone's version of the desktop's Plugins > Multiplayer > Friends window,
and the same three things on it: YOUR CODE, to give to a friend; a box for
THEIR code; and the tanks this one is linked to. A friend's code works
whatever they play on - a phone or a computer - because it is the same code
and the same network (engine/tank_link.py).

Linking tanks only makes a visit possible. The squid decides for itself
whether to go, exactly as on desktop.
"""
import threading

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from . import tank_network

NO_CODE_YET = "press 'Get my code'"
GREEN, BLUE, GREY, RED = ((0.13, 0.42, 0.18, 1), (0.15, 0.45, 0.6, 1),
                          (0.3, 0.3, 0.34, 1), (0.55, 0.14, 0.14, 1))


def open_friends(app):
    """Friends - only once the player has said yes to the multiplayer risk,
    the same question the Nearby screen asks, asked once for both."""
    from .nearby_screen import with_multiplayer_consent
    with_multiplayer_consent(app, lambda: FriendsView(app).open())


def _btn(text, cb, color=BLUE, h=52):
    b = Button(text=text, font_size=sp(15), size_hint_y=None, height=dp(h),
               background_normal="", background_color=color)
    b.bind(on_release=cb)
    return b


def _text(text="", size=13, height=None, color=(0.85, 0.88, 0.94, 1), **kwargs):
    label = Label(text=text, markup=True, font_size=sp(size), halign="left", valign="top",
                  color=color, size_hint_y=None, **kwargs)
    if height is None:      # as tall as its words, at whatever width it is given
        label.bind(width=lambda *_: setattr(label, "text_size", (label.width, None)),
                   texture_size=lambda *_: setattr(label, "height", label.texture_size[1] + dp(4)))
    else:
        label.height = dp(height)
        label.bind(size=lambda *_: setattr(label, "text_size", label.size))
    return label


def _heading(text):
    return _text(f"[b]{text}[/b]", size=15, height=26, color=(1, 1, 1, 1))


class FriendsView(Popup):
    def __init__(self, app, **kwargs):
        self.app = app
        self._finding = None
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        super().__init__(title="Friends - internet play", content=root,
                         size_hint=(0.96, 0.94), title_size=sp(18), **kwargs)

        self.status = _text(size=14, height=40)
        self.status.halign = "center"
        self.status.valign = "middle"
        root.add_widget(self.status)

        # ---- your code -----------------------------------------------------
        root.add_widget(_heading("Your friend code"))
        self.code = Button(text=NO_CODE_YET, font_size=sp(24), bold=True, size_hint_y=None,
                           height=dp(58), background_normal="",
                           background_color=(0.1, 0.12, 0.18, 1), color=(1, 1, 1, 1))
        self.code.bind(on_release=lambda *_: self.copy_code())      # tap the code to copy it
        root.add_widget(self.code)
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.get_button = _btn("Get my code", lambda *_: self.get_code(), GREEN)
        self.copy_button = _btn("Copy", lambda *_: self.copy_code(), BLUE)
        self.new_button = _btn("New code", lambda *_: self.new_code(), GREY)
        for button in (self.get_button, self.copy_button, self.new_button):
            row.add_widget(button)
        root.add_widget(row)
        self.code_note = _text(
            "Give this to a friend. It tells their game where your tank is, so it "
            "contains your internet address - only give it to someone you would "
            "give that to.", size=12)
        root.add_widget(self.code_note)

        # ---- their code ----------------------------------------------------
        root.add_widget(_heading("Add a friend"))
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.entry = TextInput(hint_text="their friend code", multiline=False,
                               font_size=sp(18), write_tab=False,
                               padding=[dp(10), dp(13), dp(10), dp(8)])
        self.entry.bind(on_text_validate=lambda *_: self.add_friend())
        connect = _btn("Connect", lambda *_: self.add_friend(), GREEN)
        connect.size_hint_x = 0.36
        row.add_widget(self.entry)
        row.add_widget(connect)
        root.add_widget(row)
        self.message = _text(size=13, color=(0.7, 0.9, 0.75, 1))
        root.add_widget(self.message)

        # ---- who is linked -------------------------------------------------
        root.add_widget(_heading("Linked tanks"))
        self._list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self._list.bind(minimum_height=self._list.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self._list)
        root.add_widget(scroll)
        self._rows = None

        root.add_widget(_text(
            "[b]If nothing happens:[/b] home routers only let in traffic from somewhere "
            "your game has just sent to, so [b]both[/b] of you enter each other's code. "
            "Your squid still decides for itself whether to visit. A tank holds its own "
            "squid and up to three visitors.", size=12, color=(0.7, 0.73, 0.8, 1)))

        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.power = _btn("", lambda *_: self.toggle_network(), RED)
        row.add_widget(self.power)
        row.add_widget(_btn("Close", lambda *_: self.dismiss(), GREY))
        root.add_widget(row)

        self._tick = Clock.schedule_interval(lambda dt: self.refresh(), 1.0)
        self.bind(on_dismiss=lambda *_: self._tick.cancel())
        if tank_network.link_of(app) is None:
            self._go_online()          # opening Friends is asking for multiplayer
        self.refresh()

    # ------------------------------------------------------------------ link
    @property
    def link(self):
        return tank_network.link_of(self.app)

    def _go_online(self):
        if tank_network.start(self.app) is None:
            self.message.text = ("[color=ff8888]Could not open the network. Is this "
                                 "device connected?[/color]")

    def toggle_network(self):
        if self.link is None:
            self._go_online()
        else:
            tank_network.stop(self.app)
            self.code.text = NO_CODE_YET
            self.message.text = ("Multiplayer is off. Your squid is home and no tank "
                                 "can reach this one.")
        self.refresh()

    # ------------------------------------------------------------- your code
    def get_code(self):
        """Ask for the tank's outside address without freezing the screen."""
        link = self.link
        if link is None or (self._finding is not None and self._finding.is_alive()):
            return
        self.code_note.text = "Asking what your address is..."
        self._finding = threading.Thread(target=link.find_friend_code,
                                         name="FriendCode", daemon=True)
        self._finding.start()

    def copy_code(self):
        """Put the friend code on the clipboard. True if there was one."""
        link = self.link
        if link is None or self.code.text == NO_CODE_YET:
            self.message.text = "There is no code yet - press 'Get my code' first."
            return False
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(self.code.text)
        self.message.text = ("Friend code copied - paste it into a message to "
                             "your friend.")
        return True

    def new_code(self):
        link = self.link
        if link is None:
            return
        self.code.text = link.new_friend_code()
        self.message.text = "New code made. The old one no longer works."

    # ------------------------------------------------------------ their code
    def add_friend(self):
        link = self.link
        if link is None:
            self.message.text = "Multiplayer is off."
            return False
        ok, said = link.connect_to_friend(self.entry.text)
        self.message.text = said if ok else f"[color=ff8888]{said}[/color]"
        if ok:
            self.entry.text = ""
        self.refresh()
        return ok

    def remove_friend(self, ip, port):
        link = self.link
        if link is not None:
            link.forget_friend(ip, port)
        self.refresh()

    # --------------------------------------------------------------- refresh
    def refresh(self):
        link = self.link
        online = link is not None
        self.power.text = "Leave the network" if online else "Go online"
        self.power.background_color = RED if online else GREEN
        for button in (self.get_button, self.copy_button, self.new_button):
            button.disabled = not online
        self.status.text = link.status_text() if online else "Multiplayer is off."
        if not online:
            self._show_rows([])
            return
        if self._finding is not None and not self._finding.is_alive():
            self._finding = None
            self.code_note.text = link.friend_code_note()
            self.code.text = link.friend_code()
        elif self.code.text != NO_CODE_YET or link.friend_code_known():
            self.code.text = link.friend_code()
        self._show_rows(link.friends())

    def _show_rows(self, friends):
        rows = [(f["ip"], f["port"], f["state"], f["theirs"]) for f in friends]
        if rows == self._rows:
            return
        self._rows = rows
        self._list.clear_widgets()
        if not rows:
            self._list.add_widget(_text("Nobody yet.", size=13, height=28,
                                        color=(0.6, 0.63, 0.7, 1)))
        for ip, port, state, theirs in rows:
            how = "joined with your code" if theirs else "added by you"
            colour = "88ff88" if state == "connected" else "ffcc66"
            line = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
            words = _text(f"{ip}:{port}\n[color={colour}]{state}[/color]  ({how})",
                          size=13, height=46)
            words.valign = "middle"
            line.add_widget(words)
            remove = _btn("Remove", lambda *_a, ip=ip, port=port: self.remove_friend(ip, port),
                          GREY, h=46)
            remove.size_hint_x = 0.3
            line.add_widget(remove)
            self._list.add_widget(line)
