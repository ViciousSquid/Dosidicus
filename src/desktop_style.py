"""One look on Windows, macOS and Linux (X11 and Wayland).

Left to itself Qt draws a program in each system's own clothes: its own font
(Segoe UI, San Francisco, whatever the Linux desktop chose), its own widget
style, its own idea of how big a point is (96 to the inch on Windows, 72 on a
Mac), its own menu bar, its own dialogs. The same window then comes out a
different size and shape on every machine. Here the game brings its own:

  FONT     Fio UI (src/fonts, SIL Open Font License) for everything, IBM Plex
           Mono where a fixed width is wanted. Loaded from the game's folder;
           nothing is installed on the system.
  SIZE     A point is 1/96 inch everywhere, so 10 pt text is the same number
           of pixels on all three. On a dense screen (Retina, 150% Windows)
           the whole window is scaled, not just the text.
  STYLE    Qt's Fusion style with a fixed light palette, whatever the system
           theme. Dialog buttons in one order, menus in the window.
  WINDOWS  Sized from the screen's size, never from what the taskbar, dock or
           panel happens to leave.

What stays the system's: the window frame and title bar (they are drawn by
the system, not the game), emoji (each system has its own emoji font), and
writing systems Fio UI does not cover, which fall back to a system font.

prepare_qt() must run before the QApplication is made; install_style() right
after.
"""
import os
import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

UI_FONT = 'Fio UI'
MONO_FONT = 'IBM Plex Mono'
#: The size of text nothing else sets: menus, dialogs, tabs, buttons.
UI_FONT_SIZE = 10
FONT_DPI = 96
#: Screen height kept clear for the system's taskbar, dock, panel or menu bar:
#: one number, so a window that fills the screen is the same size everywhere.
SYSTEM_CHROME = 100

#: `DOSIDICUS_SCREEN=1920x1080`: lay the game out for this screen instead of
#: the one found. For taking the same picture on machines whose screens differ.
SCREEN_OVERRIDE = 'DOSIDICUS_SCREEN'

#: The light palette every window is drawn in (Fusion's own, written out so
#: no system theme can lean on it).
PALETTE = {
    'Window': '#efefef', 'WindowText': '#000000',
    'Base': '#ffffff', 'AlternateBase': '#f7f7f7',
    'ToolTipBase': '#ffffdc', 'ToolTipText': '#000000',
    'Text': '#000000', 'Button': '#efefef', 'ButtonText': '#000000',
    'BrightText': '#ffffff',
    'Highlight': '#308cc6', 'HighlightedText': '#ffffff',
    'Link': '#0000ff', 'LinkVisited': '#ff00ff',
    'Light': '#ffffff', 'Midlight': '#cacaca', 'Mid': '#b8b8b8',
    'Dark': '#9f9f9f', 'Shadow': '#767676',
    'PlaceholderText': '#808080',
}
DISABLED = {'WindowText': '#bebebe', 'Text': '#bebebe', 'ButtonText': '#bebebe',
            'Highlight': '#919191', 'PlaceholderText': '#bebebe'}
INACTIVE = {'Highlight': '#919191'}


def font_directory() -> Path:
    return Path(__file__).resolve().parent / 'fonts'


def prepare_qt():
    """Before the application exists: how big a point is, how a dense screen
    is handled, and that menus and dialogs are Qt's own. Does nothing once an
    application has been made (it would be too late)."""
    if QtWidgets.QApplication.instance() is not None:
        return False
    os.environ['QT_FONT_DPI'] = str(FONT_DPI)
    app = QtWidgets.QApplication
    # Not the desktop's fonts, colours or icon theme: the game's own.
    app.setDesktopSettingsAware(False)
    # A Mac scales a Retina screen itself; asking Qt to as well doubles it.
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, sys.platform != 'darwin')
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app.setAttribute(QtCore.Qt.AA_Use96Dpi, True)
    app.setAttribute(QtCore.Qt.AA_DontUseNativeMenuBar, True)
    app.setAttribute(QtCore.Qt.AA_DontUseNativeDialogs, True)
    QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    return True


class GameStyle(QtWidgets.QProxyStyle):
    """Fusion, with the few answers Fusion takes from the system fixed."""

    def __init__(self):
        fusion = QtWidgets.QStyleFactory.create('Fusion')
        if fusion is None:
            raise RuntimeError("Qt's Fusion style is not available")
        super().__init__(fusion)
        self.setObjectName('DosidicusFusion')
        hint = QtWidgets.QStyle
        self._hints = {
            hint.SH_DialogButtonLayout: QtWidgets.QDialogButtonBox.WinLayout,
            hint.SH_DialogButtonBox_ButtonsHaveIcons: 0,
            hint.SH_ScrollBar_Transient: 0,
            hint.SH_ComboBox_Popup: 0,
            hint.SH_UnderlineShortcut: 0,
            hint.SH_Menu_Scrollable: 0,
            hint.SH_TabBar_Alignment: int(QtCore.Qt.AlignLeft),
            hint.SH_TabBar_ElideMode: int(QtCore.Qt.ElideNone),
            hint.SH_FormLayoutFormAlignment: int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop),
            hint.SH_FormLayoutLabelAlignment: int(QtCore.Qt.AlignLeft),
            hint.SH_FormLayoutWrapPolicy: QtWidgets.QFormLayout.DontWrapRows,
            hint.SH_FormLayoutFieldGrowthPolicy: QtWidgets.QFormLayout.AllNonFixedFieldsGrow,
            hint.SH_MessageBox_CenterButtons: 0,
        }

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        fixed = self._hints.get(hint)
        if fixed is not None:
            return fixed
        return super().styleHint(hint, option, widget, returnData)


def light_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    role = QtGui.QPalette
    for group in (role.Active, role.Inactive, role.Disabled):
        for name, colour in PALETTE.items():
            palette.setColor(group, getattr(role, name), QtGui.QColor(colour))
    for name, colour in INACTIVE.items():
        palette.setColor(role.Inactive, getattr(role, name), QtGui.QColor(colour))
    for name, colour in DISABLED.items():
        palette.setColor(role.Disabled, getattr(role, name), QtGui.QColor(colour))
    return palette


def load_fonts():
    """Load every font in src/fonts. Returns the families now available."""
    loaded = set()
    for path in sorted(font_directory().glob('*.ttf')):
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            raise RuntimeError(f"Could not load the game's font: {path}")
        loaded.update(QtGui.QFontDatabase.applicationFontFamilies(font_id))
    missing = {UI_FONT, MONO_FONT} - loaded
    if missing:
        raise RuntimeError("The game's fonts are missing from src/fonts: "
                           + ', '.join(sorted(missing)))
    return loaded


def ui_font(size=UI_FONT_SIZE, weight=None, family=UI_FONT) -> QtGui.QFont:
    """The game's font at a point size (a point is 1/96 inch everywhere)."""
    font = QtGui.QFont(family, int(size))
    if weight is not None:
        font.setWeight(weight)
    # Unhinted, letters keep the widths the font gives them; hinted, each
    # system's rasteriser rounds them its own way and lines break differently.
    font.setHintingPreference(QtGui.QFont.PreferNoHinting)
    return font


def install_style(app):
    """Once, right after the application is made and before any window."""
    if getattr(app, '_dosidicus_style', None) is not None:
        return False
    load_fonts()
    # A hard-coded family from older code or a plugin still lands on ours.
    for family in ('Arial', 'Helvetica', 'Verdana', 'Segoe UI', 'Sans Serif', 'sans-serif'):
        QtGui.QFont.insertSubstitution(family, UI_FONT)
    for family in ('Courier New', 'Courier', 'Consolas', 'Menlo', 'monospace', 'Monospace'):
        QtGui.QFont.insertSubstitution(family, MONO_FONT)
    style = GameStyle()
    app.setStyle(style)
    app._dosidicus_style = style            # the application does not keep it alive
    app.setPalette(light_palette())
    app.setLayoutDirection(QtCore.Qt.LeftToRight)
    font = ui_font()
    app.setFont(font)
    # These take their font from the system, not from the application.
    for widget_class in ('QMenu', 'QMenuBar', 'QMessageBox', 'QMdiSubWindowTitleBar',
                         'QTipLabel', 'QDockWidgetTitle', 'QStatusBar'):
        app.setFont(font, widget_class)
    QtWidgets.QToolTip.setFont(font)
    QtWidgets.QToolTip.setPalette(app.palette())
    return True


def _override():
    text = os.environ.get(SCREEN_OVERRIDE, '').lower().strip()
    try:
        width, height = (int(part) for part in text.split('x'))
    except ValueError:
        return None
    return (width, height) if width >= 320 and height >= 240 else None


def screen_size(screen):
    """(width, height, ratio): the screen as it reports itself and its real
    pixels per reported pixel - or the screen named in DOSIDICUS_SCREEN."""
    assumed = _override()
    if assumed:
        return assumed[0], assumed[1], 1.0
    size = screen.size()
    return size.width(), size.height(), max(1.0, float(screen.devicePixelRatio() or 1.0))


def reported_size(screen):
    """The screen's size as a QSize, as the screen reports it (or the screen
    named in DOSIDICUS_SCREEN)."""
    width, height, _ratio = screen_size(screen)
    return QtCore.QSize(width, height)


def usable_size(screen):
    """(width, height) a window may fill, the same on every system for the
    same screen: the whole width, and the height less a fixed allowance for
    whatever bar or dock the system keeps."""
    width, height, _ratio = screen_size(screen)
    return width, max(240, height - SYSTEM_CHROME)


def describe(app):
    """What is actually in force - for a screenshot's notes and the tests."""
    font = app.font()
    info = QtGui.QFontInfo(font)
    metrics = QtGui.QFontMetrics(font)
    screen = app.primaryScreen()
    return {
        'style': app.style().objectName(),
        'font_asked': font.family(), 'font_used': info.family(),
        'font_point_size': font.pointSize(), 'font_pixel_size': info.pixelSize(),
        'line_height': metrics.height(),
        'sample_width': metrics.horizontalAdvance('The squid can see a plant 0123456789'),
        'logical_dpi': round(screen.logicalDotsPerInch(), 2) if screen else None,
        'device_pixel_ratio': screen.devicePixelRatio() if screen else None,
        'screen': [screen.size().width(), screen.size().height()] if screen else None,
        'screen_assumed': list(_override() or ()) or None,
        'window_colour': app.palette().color(QtGui.QPalette.Window).name(),
        'platform': app.platformName(),
    }


__all__ = ['UI_FONT', 'MONO_FONT', 'UI_FONT_SIZE', 'prepare_qt', 'install_style',
           'load_fonts', 'ui_font', 'light_palette', 'screen_size', 'reported_size',
           'usable_size',
           'describe', 'GameStyle', 'font_directory']
