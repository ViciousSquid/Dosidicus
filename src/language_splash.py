# File: language_splash.py
"""The first thing Dosidicus shows: a language picker and OK.

main.py shows it before the game itself is even imported, and nothing else
starts until a language is chosen - so every window, prompt and tutorial
question after it (the "Show tutorial?" prompt included) is in that language.
The chosen language is preselected next time and saved to config.ini
([General] language), where Preferences reads and writes it too.

Its look - the grey bar, the bold monospace, the orange button - is shared
(scale_factor, splash_font, grey_bar, white_foot, orange_button, centre_on):
the tutorial question is drawn the same way (main.TimedMessageBox).

Light on purpose: PyQt5, the config manager and the localisation table only.
"""

import importlib
import os
import pkgutil
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

#: The splash at 100%, in the mockup's proportions.
WIDTH, BAR_HEIGHT, FOOT_HEIGHT = 352, 64, 62
BAR_GREY = '#c4c4c4'
OK_ORANGE, OK_HOVER, OK_PRESSED = '#f7841f', '#ff9a3d', '#d96d10'


def available_languages() -> List[Tuple[str, str]]:
    """[(code, native name)] of every translation shipped, by code.

    Read from the translations package itself - not only from .py files on
    disk, which a compiled build does not have - and named by each file's
    LANGUAGE_HEADER ("de - Deutsch").
    """
    codes = set()
    try:
        import translations
        codes.update(m.name for m in pkgutil.iter_modules(translations.__path__))
    except Exception:
        pass
    try:
        from .localisation import Localisation
        codes.update(Localisation.instance().get_available_languages())
    except Exception:
        pass
    found = []
    for code in sorted(c for c in codes if not c.startswith('_')):
        try:
            header = str(importlib.import_module(f'translations.{code}').LANGUAGE_HEADER)
        except Exception:
            continue
        name = header.split(' - ', 1)[1].strip() if ' - ' in header else code
        found.append((code, name or code))
    return found


def _image(*parts) -> str:
    for base in (Path(__file__).resolve().parent.parent, Path.cwd()):
        path = base.joinpath(*parts)
        if path.exists():
            return str(path)
    return os.path.join(*parts)


#: A heavy monospace, as in the mockup: the first of these the system has.
MONOSPACE = ('Consolas', 'Menlo', 'DejaVu Sans Mono', 'Liberation Mono', 'Courier New')


def _monospace_family() -> str:
    installed = set(QtGui.QFontDatabase().families())
    for family in MONOSPACE:
        if family in installed:
            return family
    return QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont).family()


def scale_factor() -> float:
    """The splash's scale: 1 at 96 dpi, more on denser screens."""
    screen = QtWidgets.QApplication.primaryScreen()
    return max(1.0, (screen.logicalDotsPerInch() / 96.0) if screen else 1.0)


def splash_font(pixel_size: float, bold: bool = True) -> QtGui.QFont:
    """The splash's monospace, at a size already scaled."""
    font = QtGui.QFont(_monospace_family())
    font.setBold(bold)
    font.setPixelSize(max(1, int(round(pixel_size))))
    return font


def orange_button(text: str, f: float, width: float = 170) -> QtWidgets.QPushButton:
    """The splash's button: orange, edged in black, bold monospace."""
    def s(value):
        return int(round(value * f))
    button = QtWidgets.QPushButton(text)
    button.setCursor(QtCore.Qt.PointingHandCursor)
    button.setFixedSize(s(width), s(48))
    button.setStyleSheet(
        f"QPushButton {{ background: {OK_ORANGE}; color: black; border: {s(3)}px solid black;"
        f" border-radius: {s(12)}px; font-family: '{_monospace_family()}'; font-weight: bold;"
        f" font-size: {s(26)}px; }}"
        f"QPushButton:hover {{ background: {OK_HOVER}; }}"
        f"QPushButton:pressed {{ background: {OK_PRESSED}; }}")
    return button


def grey_bar(text: str, f: float) -> QtWidgets.QLabel:
    """The splash's grey bar, carrying a line of text instead of the picker."""
    def s(value):
        return int(round(value * f))
    label = QtWidgets.QLabel(text)
    label.setAlignment(QtCore.Qt.AlignCenter)
    label.setWordWrap(True)
    label.setFont(splash_font(s(24)))
    label.setFixedWidth(s(WIDTH))
    label.setMinimumHeight(s(BAR_HEIGHT))
    label.setStyleSheet(f"background: {BAR_GREY}; color: black; padding: {s(8)}px {s(14)}px;")
    return label


def white_foot(f: float) -> QtWidgets.QWidget:
    foot = QtWidgets.QWidget()
    foot.setFixedWidth(int(round(WIDTH * f)))
    foot.setMinimumHeight(int(round(FOOT_HEIGHT * f)))
    foot.setStyleSheet('background: white;')
    return foot


def centre_on(window: QtWidgets.QWidget, over: Optional[QtWidgets.QWidget] = None) -> None:
    """Centre a window over another that is showing, else on the screen."""
    if over is not None and over.isVisible():
        area = over.frameGeometry()
    else:
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
    frame = window.frameGeometry()
    frame.moveCenter(area.center())
    window.move(frame.topLeft())


class _LanguageBar(QtWidgets.QComboBox):
    """The grey bar: the chosen language centred, a black triangle at the right."""

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor(BAR_GREY))
        if self.hasFocus():
            pen = QtGui.QPen(QtGui.QColor(OK_ORANGE), 2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        painter.setPen(QtCore.Qt.black)
        painter.setFont(self.font())
        painter.drawText(rect, QtCore.Qt.AlignCenter, self.currentText())
        side = rect.height() * 0.32
        cx, cy = rect.right() - rect.height() * 0.6, rect.center().y()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtCore.Qt.black)
        painter.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(cx - side / 2, cy - side * 0.4),
            QtCore.QPointF(cx + side / 2, cy - side * 0.4),
            QtCore.QPointF(cx, cy + side * 0.45)]))


class LanguageSplash(QtWidgets.QDialog):
    """The language bar and OK. Accepted only by OK (or Enter)."""

    def __init__(self, languages: List[Tuple[str, str]], current: str = 'en'):
        super().__init__(None, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setWindowTitle('Dosidicus')
        icon = _image('images', 'icons', 'squidblack.png')
        if os.path.exists(icon):
            self.setWindowIcon(QtGui.QIcon(icon))
        f = scale_factor()

        def s(value):
            return int(round(value * f))

        self.languages = list(languages)
        self.bar = _LanguageBar()
        self.bar.setFixedSize(s(WIDTH), s(BAR_HEIGHT))
        font = splash_font(s(30))
        self.bar.setFont(font)
        for code, name in self.languages:
            self.bar.addItem(name, code)
        index = self.bar.findData(current)
        self.bar.setCurrentIndex(index if index >= 0 else max(0, self.bar.findData('en')))
        listing = QtGui.QFont(font)
        listing.setPixelSize(s(22))
        self.bar.view().setFont(listing)
        self.bar.setStyleSheet(
            f'QComboBox QAbstractItemView {{ background: white; color: black; outline: 0;'
            f' selection-background-color: {OK_ORANGE}; selection-color: black; }}')

        self.ok = orange_button('OK', f)
        self.ok.setDefault(True)
        self.ok.setAutoDefault(True)
        self.ok.clicked.connect(self.accept)

        foot = white_foot(f)
        foot.setFixedHeight(s(FOOT_HEIGHT))
        foot_layout = QtWidgets.QHBoxLayout(foot)
        foot_layout.addWidget(self.ok, 0, QtCore.Qt.AlignCenter)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for widget in (self.bar, foot):
            layout.addWidget(widget)
        self.setFixedSize(self.sizeHint())
        self.ok.setFocus()
        centre_on(self)

    def language(self) -> str:
        return self.bar.currentData() or 'en'

    def keyPressEvent(self, event):
        # Escape does not skip the choice: nothing starts until there is one.
        if event.key() == QtCore.Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)


def choose_language(config_manager=None) -> Optional[str]:
    """Show the splash until a language is chosen; apply and save it.

    Returns the language code, or None if the splash was closed without one
    (the caller then quits). With no translations to choose from, the
    configured language stands.
    """
    from .config_manager import ConfigManager
    from .localisation import Localisation
    config = config_manager or ConfigManager()
    current = config.get_language()
    languages = available_languages()
    if not languages:
        return current
    splash = LanguageSplash(languages, current)
    splash.show()
    splash.raise_()
    splash.activateWindow()
    if splash.exec_() != QtWidgets.QDialog.Accepted:
        return None
    code = splash.language()
    if not config.config.has_section('General'):
        config.config.add_section('General')
    config.config.set('General', 'language', code)
    config._save_config()
    Localisation.instance().set_language(code)
    return code


__all__ = ['available_languages', 'LanguageSplash', 'choose_language', 'scale_factor',
           'splash_font', 'orange_button', 'grey_bar', 'white_foot', 'centre_on']
