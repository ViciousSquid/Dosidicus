"""Choose a slot: three tanks, each with its own squid.

Shown as the game starts, after the language is chosen, and from the File
menu while playing. Drawn in the family of the language splash and the
tutorial question (src/language_splash.py): the question on the grey bar in
heavy monospace, black-edged blocks beneath it on white, dark red for what
destroys. An empty slot is pastel green and says New game; a slot in use is
pastel orange and carries its squid's name.

The dialog only chooses. It deletes a squid when asked twice, through
SaveSlots; what choosing a slot does to the running game is main.py's.
"""
from typing import List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from .language_splash import (GREEN, RED, BAR_GREY, centre_on, grey_bar, scale_factor,
                              splash_button, splash_font)
from .localisation import Localisation
from .save_slots import SLOTS, SaveSlots

WIDTH = 420                      # at 100%
ROW_WIDTH, ROW_HEIGHT, NUMBER_WIDTH = 356, 76, 86
#: (face, hover) - an empty slot, a slot in use, and one about to be deleted.
PASTEL_GREEN = ('#bfe8bd', '#a9dca6')
PASTEL_ORANGE = ('#f9cfa0', '#f3bd82')
PASTEL_RED = ('#f3aaaa', '#ea8f8f')
NUMBER_FACE = '#f4f6e6'
INK = '#16181c'


def age_text(seconds) -> str:
    seconds = max(0, int(float(seconds or 0)))
    days, hours, minutes = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
    if days:
        return f'{days}d {hours}h'
    if hours:
        return f'{hours}h {minutes:02d}m'
    return f'{minutes}m'


class SlotRow(QtWidgets.QAbstractButton):
    """One slot: its number, large, and who is in it."""

    def __init__(self, entry: dict, f: float, parent=None):
        super().__init__(parent)
        self.f = f
        self.entry = dict(entry)
        self.playing = False
        self.doomed = False              # shown in red while choosing what to delete
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFixedSize(int(round(ROW_WIDTH * f)), int(round(ROW_HEIGHT * f)))
        self.setAccessibleName(self.title())

    def title(self) -> str:
        loc = Localisation.instance()
        if self.entry.get('empty'):
            return loc.get('slot_new_game', 'New game')
        return self.entry.get('name') or loc.get('slot_unnamed', 'Squid')

    def detail(self) -> str:
        loc = Localisation.instance()
        if self.entry.get('empty'):
            return ''
        parts = []
        personality = self.entry.get('personality')
        if personality:
            parts.append(loc.get(f'personality_{personality}', personality.capitalize()))
        stage = self.entry.get('stage')
        if stage in ('dead', 'parent'):
            parts.append(loc.get(f'slot_stage_{stage}', stage))
        parts.append(age_text(self.entry.get('age_seconds')))
        if self.playing:
            parts.append(loc.get('slot_playing', 'playing'))
        return ' · '.join(parts)

    def colours(self):
        if self.doomed and not self.entry.get('empty'):
            return PASTEL_RED
        return PASTEL_GREEN if self.entry.get('empty') else PASTEL_ORANGE

    def paintEvent(self, event):
        f = self.f

        def s(value):
            return int(round(value * f))
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        edge = s(3)
        rect = QtCore.QRectF(self.rect()).adjusted(edge / 2, edge / 2, -edge / 2, -edge / 2)
        face, hover = self.colours()
        lit = self.isEnabled() and (self.underMouse() or self.hasFocus())
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, s(12), s(12))
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QtGui.QColor(hover if lit else face))
        number = QtCore.QRectF(0, 0, s(NUMBER_WIDTH), self.height())
        painter.fillRect(number, QtGui.QColor(NUMBER_FACE))
        painter.setClipping(False)
        painter.setPen(QtGui.QPen(QtCore.Qt.black, edge))
        painter.drawLine(QtCore.QPointF(number.right(), edge), QtCore.QPointF(number.right(), self.height() - edge))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(rect, s(12), s(12))
        if self.hasFocus():                  # the row the keyboard is on
            painter.setPen(QtGui.QPen(QtGui.QColor(GREEN[0]), s(2), QtCore.Qt.DotLine))
            painter.drawRoundedRect(rect.adjusted(s(5), s(5), -s(5), -s(5)), s(8), s(8))
        ink = QtGui.QColor(INK)
        if not self.isEnabled():
            ink.setAlpha(90)
        painter.setPen(ink)
        painter.setFont(splash_font(s(50)))
        painter.drawText(number, QtCore.Qt.AlignCenter, str(self.entry.get('slot', '')))
        words = QtCore.QRectF(number.right() + s(10), 0, self.width() - number.right() - s(18), self.height())
        detail = self.detail()
        title_font = splash_font(s(26))
        title = QtGui.QFontMetricsF(title_font).elidedText(self.title(), QtCore.Qt.ElideRight, words.width())
        painter.setFont(title_font)
        if detail:
            painter.drawText(words.adjusted(0, s(10), 0, -s(30)), QtCore.Qt.AlignCenter, title)
            small = splash_font(s(13), bold=False)
            painter.setFont(small)
            painter.drawText(words.adjusted(0, s(44), 0, -s(8)), QtCore.Qt.AlignCenter,
                             QtGui.QFontMetricsF(small).elidedText(detail, QtCore.Qt.ElideRight, words.width()))
        else:
            painter.drawText(words, QtCore.Qt.AlignCenter, title)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class SlotChooser(QtWidgets.QDialog):
    """Returns the slot chosen in `self.chosen` (None: left as it was)."""

    def __init__(self, slots: SaveSlots, parent=None, playing: Optional[int] = None):
        flags = QtCore.Qt.Dialog if parent is not None else QtCore.Qt.Window
        super().__init__(parent, flags | QtCore.Qt.FramelessWindowHint)
        self.slots = slots
        self.playing = playing           # the slot the running game is in, if a game is running
        self.chosen: Optional[int] = None
        self.deleting = False
        self.doomed: Optional[int] = None
        self.loc = Localisation.instance()
        self.setWindowTitle(self.loc.get('slot_choose', 'Choose a slot'))
        self.setModal(True)
        f = self.f = scale_factor()

        def s(value):
            return int(round(value * f))
        self.setStyleSheet('QDialog { background: white; }')
        self.bar = grey_bar('', f)
        self.bar.setFixedWidth(s(WIDTH))

        self.rows: List[SlotRow] = []
        self.body = QtWidgets.QVBoxLayout()
        self.body.setContentsMargins(0, s(14), 0, s(6))
        self.body.setSpacing(s(8))

        self.delete_button = splash_button(self.loc.get('slot_delete', 'Delete'), f, RED, width=150)
        self.back_button = splash_button(self.loc.get('slot_back', 'Back'), f, GREEN, width=150)
        self.yes_button = splash_button(self.loc.get('yes', 'Yes'), f, RED, width=150)
        self.no_button = splash_button(self.loc.get('no', 'No'), f, GREEN, width=150)
        for button in (self.delete_button, self.back_button, self.yes_button, self.no_button):
            button.setAutoDefault(False)
        self.delete_button.clicked.connect(self.begin_deleting)
        self.back_button.clicked.connect(self.back)
        self.yes_button.clicked.connect(self.delete_confirmed)
        self.no_button.clicked.connect(self.stop_deleting)
        foot = QtWidgets.QHBoxLayout()
        foot.setContentsMargins(s(32), s(6), s(32), s(16))
        foot.setSpacing(s(16))
        foot.addWidget(self.delete_button)
        foot.addWidget(self.yes_button)
        foot.addStretch(1)
        foot.addWidget(self.no_button)
        foot.addWidget(self.back_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.bar)
        layout.addLayout(self.body)
        layout.addLayout(foot)
        self.fill()
        self.setFixedSize(self.sizeHint())
        centre_on(self, parent)

    # -------------------------------------------------------------- contents
    def fill(self):
        """Draw the slots as they are on disk now."""
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.rows = []
        entries = self.slots.describe()
        for entry in entries:
            row = SlotRow(entry, self.f)
            row.playing = self.playing == entry['slot']
            row.clicked.connect(lambda _checked=False, number=entry['slot']: self.pick(number))
            self.rows.append(row)
            self.body.addWidget(row, 0, QtCore.Qt.AlignHCenter)
        self.show_state()
        focus = next((r for r in self.rows if r.entry['active']), self.rows[0])
        focus.setFocus()

    def deletable(self, row: SlotRow) -> bool:
        """A squid can be deleted unless it is the one being played."""
        return not row.entry.get('empty') and row.entry['slot'] != self.playing

    def show_state(self):
        confirming = self.doomed is not None
        if confirming:
            row = self.rows[self.doomed - 1]
            text = self.loc.get('slot_delete_confirm', 'Delete {name}?', name=row.title())
        elif self.deleting:
            text = self.loc.get('slot_delete_which', 'Delete which?')
        else:
            text = self.loc.get('slot_choose', 'Choose a slot')
        self.bar.setText(text)
        pad = int(round(8 * self.f)), int(round(14 * self.f))
        self.bar.setStyleSheet(
            f"background: {BAR_GREY}; color: {RED[0] if (self.deleting or confirming) else 'black'};"
            f" padding: {pad[0]}px {pad[1]}px;")
        for row in self.rows:
            row.doomed = (self.deleting and self.deletable(row)) if not confirming \
                else row.entry['slot'] == self.doomed
            row.setEnabled(self.deletable(row) if self.deleting and not confirming
                           else (not confirming))
            row.update()
        self.delete_button.setVisible(not self.deleting and not confirming)
        self.delete_button.setEnabled(any(self.deletable(row) for row in self.rows))
        self.yes_button.setVisible(confirming)
        self.no_button.setVisible(confirming)
        # At the start there is nothing to go back to: a slot must be chosen.
        self.back_button.setVisible(not confirming and (self.deleting or self.playing is not None))

    # --------------------------------------------------------------- actions
    def pick(self, number: int):
        row = self.rows[number - 1]
        if self.doomed is not None:
            return
        if self.deleting:
            if self.deletable(row):
                self.doomed = number
                self.show_state()
                self.no_button.setFocus()
            return
        self.chosen = number
        self.accept()

    def begin_deleting(self):
        self.deleting, self.doomed = True, None
        self.show_state()
        target = next((row for row in self.rows if self.deletable(row)), None)
        if target is not None:
            target.setFocus()

    def stop_deleting(self):
        self.deleting, self.doomed = False, None
        self.show_state()
        self.rows[0].setFocus()

    def delete_confirmed(self):
        if self.doomed is not None and self.deletable(self.rows[self.doomed - 1]):
            removed = self.slots.delete(self.doomed)
            print(f"[Slots] Deleted the squid in slot {self.doomed}: {removed} file(s)")
        self.deleting, self.doomed = False, None
        self.fill()

    def back(self):
        if self.deleting:
            self.stop_deleting()
        else:
            self.reject()

    def keyPressEvent(self, event):
        key = event.key()
        if QtCore.Qt.Key_1 <= key < QtCore.Qt.Key_1 + SLOTS:
            row = self.rows[key - QtCore.Qt.Key_1]
            if row.isEnabled():
                self.pick(row.entry['slot'])
            return
        if key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
            live = [row for row in self.rows if row.isEnabled()]
            if live:
                current = next((i for i, row in enumerate(live) if row.hasFocus()), -1)
                step = 1 if key == QtCore.Qt.Key_Down else -1
                live[(current + step) % len(live)].setFocus()
            return
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
            focused = next((row for row in self.rows if row.hasFocus() and row.isEnabled()), None)
            if focused is not None:
                self.pick(focused.entry['slot'])
                return
        if key == QtCore.Qt.Key_Escape:
            if self.doomed is not None or self.deleting:
                self.stop_deleting()
            elif self.playing is not None:
                self.reject()
            # At the start Escape does not skip the choice.
            return
        super().keyPressEvent(event)


def choose_slot(slots: SaveSlots, parent=None, playing: Optional[int] = None) -> Optional[int]:
    """Show the chooser; the slot picked, or None if it was left alone."""
    dialog = SlotChooser(slots, parent, playing)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None
    return dialog.chosen


__all__ = ['SlotChooser', 'SlotRow', 'choose_slot', 'age_text', 'PASTEL_GREEN', 'PASTEL_ORANGE']
