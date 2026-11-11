"""Save slots on the phone: three tanks, each with its own squid.

The same slots the desktop has (src/save_slots.py), drawn the same way: a
large number, pastel green and "New game" for an empty slot, pastel orange
and the squid's name for one in use, dark red for Delete, which asks twice
and never deletes the squid being played.
"""
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup

PASTEL_GREEN = (0.749, 0.910, 0.741, 1)        # #bfe8bd, as on the desktop
PASTEL_ORANGE = (0.976, 0.812, 0.627, 1)       # #f9cfa0
PASTEL_RED = (0.953, 0.667, 0.667, 1)          # #f3aaaa
NUMBER_FACE = (0.957, 0.965, 0.902, 1)
DARK_RED = (0.62, 0.11, 0.11, 1)
DARK_GREEN = (0.12, 0.43, 0.19, 1)
INK = (0.086, 0.094, 0.110, 1)


def age_text(seconds):
    seconds = max(0, int(float(seconds or 0)))
    days, hours, minutes = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
    if days:
        return f'{days}d {hours}h'
    if hours:
        return f'{hours}h {minutes:02d}m'
    return f'{minutes}m'


def row_text(entry, playing):
    """What a slot's row says: (title, detail)."""
    if entry.get('empty'):
        return 'New game', ''
    parts = [str(entry.get('personality') or '').capitalize()]
    if entry.get('stage') in ('dead', 'parent'):
        parts.append(entry['stage'])
    parts.append(age_text(entry.get('age_seconds')))
    if playing:
        parts.append('playing')
    return entry.get('name') or 'Squid', ' · '.join(part for part in parts if part)


def _edged(widget, colour):
    """A flat block of colour with a black edge, like the desktop's rows."""
    with widget.canvas.before:
        widget._face_colour = Color(*colour)
        widget._face = Rectangle(pos=widget.pos, size=widget.size)
    with widget.canvas.after:
        Color(0, 0, 0, 1)
        widget._edge = Line(rectangle=(*widget.pos, *widget.size), width=dp(1.4))

    def follow(*_):
        widget._face.pos, widget._face.size = widget.pos, widget.size
        widget._edge.rectangle = (*widget.pos, *widget.size)
    widget.bind(pos=follow, size=follow)
    return widget


class SlotsView(BoxLayout):
    """The three rows and Delete. `on_open(slot)` is called with a choice."""

    def __init__(self, slots, playing, on_open, on_close=None, **kwargs):
        super().__init__(orientation='vertical', spacing=dp(8), padding=dp(10), **kwargs)
        self.slots, self.playing = slots, playing
        self.on_open, self.on_close = on_open, on_close
        self.deleting = False
        self.doomed = None
        self.heading = Label(font_size=sp(20), bold=True, size_hint_y=None, height=dp(40))
        self.rows_box = BoxLayout(orientation='vertical', spacing=dp(8))
        self.foot = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(10))
        for widget in (self.heading, self.rows_box, self.foot):
            self.add_widget(widget)
        self.rows = []
        self.fill()

    def deletable(self, entry):
        return not entry.get('empty') and entry['slot'] != self.playing

    def fill(self):
        self.entries = self.slots.describe()
        self.rows_box.clear_widgets()
        self.foot.clear_widgets()
        self.rows = []
        confirming = self.doomed is not None
        if confirming:
            name = row_text(self.entries[self.doomed - 1], False)[0]
            self.heading.text, self.heading.color = f'Delete {name}?', (1, 0.45, 0.45, 1)
        elif self.deleting:
            self.heading.text, self.heading.color = 'Delete which?', (1, 0.45, 0.45, 1)
        else:
            self.heading.text, self.heading.color = 'Choose a slot', (1, 1, 1, 1)
        for entry in self.entries:
            self.rows_box.add_widget(self._row(entry, confirming))
        if confirming:
            self.foot.add_widget(self._button('Yes', DARK_RED, self.delete_confirmed))
            self.foot.add_widget(self._button('No', DARK_GREEN, self.stop_deleting))
        elif self.deleting:
            self.foot.add_widget(self._button('Back', DARK_GREEN, self.stop_deleting))
        else:
            delete = self._button('Delete', DARK_RED, self.begin_deleting)
            delete.disabled = not any(self.deletable(entry) for entry in self.entries)
            self.foot.add_widget(delete)
            self.foot.add_widget(self._button('Back', DARK_GREEN, lambda *_: self.on_close and self.on_close()))

    def _button(self, text, colour, action):
        button = Button(text=text, font_size=sp(18), bold=True, background_normal='',
                        background_color=colour)
        button.bind(on_release=lambda *_: action())
        return button

    def _row(self, entry, confirming):
        number = entry['slot']
        title, detail = row_text(entry, number == self.playing)
        if confirming:
            live, colour = False, PASTEL_RED if number == self.doomed else None
        elif self.deleting:
            live = self.deletable(entry)
            colour = PASTEL_RED if live else None
        else:
            live, colour = True, None
        colour = colour or (PASTEL_GREEN if entry.get('empty') else PASTEL_ORANGE)
        row = BoxLayout(size_hint_y=None, height=dp(78))
        digit = _edged(Label(text=str(number), font_size=sp(40), bold=True, color=INK,
                             size_hint_x=None, width=dp(74)), NUMBER_FACE)
        words = Button(markup=True, halign='center', valign='middle', background_normal='',
                       background_down='', background_color=(0, 0, 0, 0), color=INK,
                       text=f'[b][size={int(sp(22))}]{title}[/size][/b]'
                            + (f'\n[size={int(sp(13))}]{detail}[/size]' if detail else ''))
        words.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        _edged(words, colour)
        words.disabled = not live
        words.disabled_color = (INK[0], INK[1], INK[2], 0.45)
        words.background_disabled_normal = ''
        words.bind(on_release=lambda *_: self.pick(number))
        row.add_widget(digit)
        row.add_widget(words)
        row.slot, row.title, row.detail, row.colour, row.button = number, title, detail, colour, words
        self.rows.append(row)
        return row

    # --------------------------------------------------------------- actions
    def pick(self, number):
        entry = self.entries[number - 1]
        if self.doomed is not None:
            return
        if self.deleting:
            if self.deletable(entry):
                self.doomed = number
                self.fill()
            return
        self.on_open(number)

    def begin_deleting(self):
        self.deleting, self.doomed = True, None
        self.fill()

    def stop_deleting(self):
        self.deleting, self.doomed = False, None
        self.fill()

    def delete_confirmed(self):
        if self.doomed is not None and self.deletable(self.entries[self.doomed - 1]):
            self.slots.delete(self.doomed)
        self.deleting, self.doomed = False, None
        self.fill()


def open_slots(app):
    """Menu > Save slots."""
    popup = Popup(title='Save slots', size_hint=(0.92, None), height=dp(470), title_size=sp(18))

    def chosen(number):
        popup.dismiss()
        app.open_slot(number)
    popup.content = SlotsView(app.slots, app.slots.active, chosen, popup.dismiss)
    popup.open()
    return popup
