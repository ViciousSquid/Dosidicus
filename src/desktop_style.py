"""One look on Windows, macOS and Linux (X11 and Wayland).

Left to itself Qt draws a program in each system's own clothes: its own font
(Segoe UI, San Francisco, whatever the Linux desktop chose), its own widget
style, its own idea of how big a point is (96 to the inch on Windows, 72 on a
Mac), its own menu bar, its own dialogs. The same window then comes out a
different size and shape on every machine. Here the game brings its own:

  FONT     Fio UI (src/fonts, SIL Open Font License) for everything, IBM Plex
           Mono where a fixed width is wanted, and the game's own emoji.
           Loaded from the game's folder; nothing is installed on the system.
  TEXT     One text engine (FreeType) measures and draws it on all three.
  SIZE     A point is 1/96 inch everywhere, so 10 pt text is the same number
           of pixels on all three. On a dense screen (Retina, 150% Windows)
           the whole window is scaled, not just the text.
  STYLE    Qt's Fusion style with a fixed light palette, whatever the system
           theme. Dialog buttons in one order, menus in the window.
  WINDOWS  Sized from the screen's size, never from what the taskbar, dock or
           panel happens to leave.

What stays the system's: the window frame and title bar (they are drawn by
the system, not the game); an emoji the game itself does not use, typed by a
player; and writing systems Fio UI does not cover, which fall back to a
system font. Shortcuts are the same keys everywhere, a Mac included: Ctrl is
the Control key there, not Command.

prepare_qt() must run before the QApplication is made; install_style() right
after.
"""
import os
import sys
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

UI_FONT = 'Fio UI'
MONO_FONT = 'IBM Plex Mono'
#: The game's own emoji: Noto Color Emoji cut down to the ones the game uses
#: (tools/subset_emoji_font.py). Each system has its own emoji font, so the
#: same button showed three different brains.
EMOJI_FONT = 'Dosidicus Emoji'
#: The same emoji as plain black-and-white line drawings (from Noto Emoji),
#: for where a quiet one is wanted: ask for this family by name.
LINE_EMOJI_FONT = 'Dosidicus Line Emoji'
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


#: Fusion's sizes at 96 DPI on a 96-DPI system (see GameStyle).
METRICS = {
    'PM_ButtonDefaultIndicator': 0, 'PM_ButtonIconSize': 16, 'PM_ButtonMargin': 6,
    'PM_ButtonShiftHorizontal': 0, 'PM_ButtonShiftVertical': 0, 'PM_CheckBoxLabelSpacing': 6,
    'PM_ComboBoxFrameWidth': 1, 'PM_DefaultChildMargin': 9, 'PM_DefaultFrameWidth': 1,
    'PM_DefaultLayoutSpacing': 6, 'PM_DefaultTopLevelMargin': 11,
    'PM_DialogButtonsButtonHeight': 30, 'PM_DialogButtonsButtonWidth': 70,
    'PM_DialogButtonsSeparator': 26, 'PM_DockWidgetFrameWidth': 1,
    'PM_DockWidgetHandleExtent': 4, 'PM_DockWidgetSeparatorExtent': 6,
    'PM_DockWidgetTitleBarButtonMargin': 2, 'PM_DockWidgetTitleMargin': 1,
    'PM_ExclusiveIndicatorHeight': 14, 'PM_ExclusiveIndicatorWidth': 14,
    'PM_FocusFrameHMargin': 2, 'PM_FocusFrameVMargin': 2,
    'PM_HeaderDefaultSectionSizeHorizontal': 100, 'PM_HeaderDefaultSectionSizeVertical': 30,
    'PM_HeaderGripMargin': 4, 'PM_HeaderMargin': 2, 'PM_HeaderMarkSize': 16,
    'PM_IconViewIconSize': 32, 'PM_IndicatorHeight': 14, 'PM_IndicatorWidth': 14,
    'PM_LargeIconSize': 32, 'PM_ListViewIconSize': 24, 'PM_MDIFrameWidth': 4,
    'PM_MDIMinimizedWidth': 196, 'PM_MdiSubWindowFrameWidth': 4,
    'PM_MdiSubWindowMinimizedWidth': 196, 'PM_MenuBarHMargin': 0, 'PM_MenuBarItemSpacing': 6,
    'PM_MenuBarPanelWidth': 0, 'PM_MenuBarVMargin': 0, 'PM_MenuButtonIndicator': 12,
    'PM_MenuDesktopFrameWidth': 0, 'PM_MenuHMargin': 0, 'PM_MenuPanelWidth': 0,
    'PM_MenuScrollerHeight': 10, 'PM_MenuTearoffHeight': 10, 'PM_MenuVMargin': 0,
    'PM_MessageBoxIconSize': 48, 'PM_ProgressBarChunkWidth': 9,
    'PM_RadioButtonLabelSpacing': 6, 'PM_ScrollBarExtent': 14, 'PM_ScrollBarSliderMin': 26,
    'PM_ScrollView_ScrollBarOverlap': 0, 'PM_ScrollView_ScrollBarSpacing': 0,
    'PM_SizeGripSize': 13, 'PM_SliderLength': 15, 'PM_SliderThickness': 15,
    'PM_SliderTickmarkOffset': 4, 'PM_SmallIconSize': 16, 'PM_SpinBoxFrameWidth': 3,
    'PM_SpinBoxSliderHeight': 2, 'PM_SplitterWidth': 4, 'PM_SubMenuOverlap': -1,
    'PM_TabBarBaseHeight': 1, 'PM_TabBarBaseOverlap': 2, 'PM_TabBarIconSize': 16,
    'PM_TabBarScrollButtonWidth': 16, 'PM_TabBarTabHSpace': 24, 'PM_TabBarTabOverlap': 1,
    'PM_TabBarTabShiftHorizontal': 0, 'PM_TabBarTabShiftVertical': 2, 'PM_TabBarTabVSpace': 12,
    'PM_TabBar_ScrollButtonOverlap': 1, 'PM_TabCloseIndicatorHeight': 20,
    'PM_TabCloseIndicatorWidth': 20, 'PM_TextCursorWidth': 1, 'PM_TitleBarButtonIconSize': 16,
    'PM_TitleBarButtonSize': 19, 'PM_TitleBarHeight': 24, 'PM_ToolBarExtensionExtent': 12,
    'PM_ToolBarFrameWidth': 2, 'PM_ToolBarHandleExtent': 9, 'PM_ToolBarIconSize': 24,
    'PM_ToolBarItemMargin': 2, 'PM_ToolBarItemSpacing': 1, 'PM_ToolBarSeparatorExtent': 6,
    'PM_ToolTipLabelFrameWidth': 2, 'PM_TreeViewIndentation': 20,
}


def font_directory() -> Path:
    return Path(__file__).resolve().parent / 'fonts'


def prepare_qt():
    """Before the application exists: how big a point is, how a dense screen
    is handled, and that menus and dialogs are Qt's own. Does nothing once an
    application has been made (it would be too late)."""
    if QtWidgets.QApplication.instance() is not None:
        return False
    os.environ['QT_FONT_DPI'] = str(FONT_DPI)
    # One text engine. Each system measures and draws letters with its own
    # (DirectWrite, CoreText, FreeType) and they round a line's height
    # differently - 17 pixels on Windows and a Mac where Linux says 18 - so
    # menus and lists came out a few pixels apart. Qt carries FreeType on all
    # three; with it the same font gives the same numbers everywhere.
    # DOSIDICUS_NATIVE_TEXT=1 keeps the system's own.
    native = {'win32': 'windows', 'darwin': 'cocoa'}.get(sys.platform)
    if (native and not os.environ.get('QT_QPA_PLATFORM')
            and os.environ.get('DOSIDICUS_NATIVE_TEXT') != '1'):
        os.environ['QT_QPA_PLATFORM'] = f'{native}:fontengine=freetype'
    app = QtWidgets.QApplication
    # Not the desktop's fonts, colours or icon theme: the game's own.
    app.setDesktopSettingsAware(False)
    # A Mac scales a Retina screen itself; asking Qt to as well doubles it.
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, sys.platform != 'darwin')
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app.setAttribute(QtCore.Qt.AA_Use96Dpi, True)
    # A Mac swaps Ctrl and Command, and names keys with symbols: the same
    # menu read "Ctrl+Shift+B" on two systems and a narrower symbol row on the
    # third. Unswapped, Ctrl+P is the Control key and P on a Mac as it is
    # everywhere else, so the menu can say so in the same words
    # (spell_out_shortcuts) and be telling the truth.
    if sys.platform == 'darwin':
        app.setAttribute(QtCore.Qt.AA_MacDontSwapCtrlAndMeta, True)
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

        # Fusion multiplies its sizes by (text DPI / the system's base DPI).
        # That is 96/96 on Windows and Linux and 96/72 on a Mac, where every
        # margin, tab and check box came out a third larger. Its own numbers,
        # as it gives them at 96/96, written out - so they are the same
        # numbers everywhere.
        self._metrics_table = {getattr(hint, name): value for name, value in METRICS.items()
                         if hasattr(hint, name)}
        self._message_icons = (hint.SP_MessageBoxInformation, hint.SP_MessageBoxWarning,
                               hint.SP_MessageBoxCritical, hint.SP_MessageBoxQuestion)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        fixed = self._hints.get(hint)
        if fixed is not None:
            return fixed
        return super().styleHint(hint, option, widget, returnData)

    def pixelMetric(self, metric, option=None, widget=None):
        fixed = self._metrics_table.get(metric)
        if fixed is not None:
            return fixed
        return super().pixelMetric(metric, option, widget)

    def standardIcon(self, standard, option=None, widget=None):
        # Windows hands back its own system icons for these four; Qt's
        # built-in ones are the same picture on every system.
        if standard in self._message_icons:
            return QtGui.QIcon(self.baseStyle().standardPixmap(standard, option, widget))
        return super().standardIcon(standard, option, widget)


def message_box_size(box):
    """The size Qt gives a message box on Windows and Linux (Qt 5's
    QMessageBoxPrivate::updateSize), on every system: a Mac wraps the text at
    420 pixels where the others wrap at 500, and ignores the title."""
    layout = box.layout()
    label = box.findChild(QtWidgets.QLabel, 'qt_msgbox_label')
    informative = box.findChild(QtWidgets.QLabel, 'qt_msgbox_informativelabel')
    if layout is None or label is None:
        return box.size()
    screen = box.screen() if hasattr(box, 'screen') else None
    screen = screen or QtGui.QGuiApplication.primaryScreen()
    available = reported_size(screen).width() if screen else 1920
    hard_limit = available if available <= 1024 else min(available - 480, 1000)
    soft_limit = min(available // 2, 500)
    policy_type = QtWidgets.QSizePolicy

    def minimum_width():
        layout.activate()
        return layout.totalMinimumSize().width()

    label.setSizePolicy(policy_type(policy_type.Preferred, policy_type.Preferred,
                                    policy_type.Label))
    if informative is not None:
        informative.setSizePolicy(policy_type.Ignored, policy_type.Ignored)
    label.setWordWrap(False)
    width = minimum_width()
    if width > soft_limit:
        label.setWordWrap(True)
        width = min(max(soft_limit, minimum_width()), hard_limit)
    if informative is not None:
        label.setSizePolicy(policy_type.Ignored, policy_type.Ignored)
        policy = policy_type(policy_type.Minimum, policy_type.Preferred)
        policy.setHeightForWidth(True)
        informative.setSizePolicy(policy)
        width = min(max(width, minimum_width()), hard_limit)
        policy.setHeightForWidth(label.wordWrap())
        label.setSizePolicy(policy)
    title = QtGui.QFontMetrics(QtWidgets.QApplication.font('QMdiSubWindowTitleBar'))
    width = max(width, min(title.horizontalAdvance(box.windowTitle()) + 50, hard_limit))
    layout.activate()
    height = (layout.totalHeightForWidth(width) if layout.hasHeightForWidth()
              else layout.totalMinimumSize().height())
    return QtCore.QSize(width, height)


def spell_out_shortcuts(menu):
    """Write each action's shortcut into its text in the same words on every
    system ("Ctrl+Shift+B"). Qt would otherwise write it the system's way,
    which on a Mac is a row of symbols - a different menu, and a narrower
    one. A menu shows what follows a tab in an action's text as its shortcut,
    and adds nothing of its own when there is one."""
    changed = 0
    for action in menu.actions():
        shortcut = action.shortcut()
        text = action.text()
        if shortcut.isEmpty() or '\t' in text or action.isSeparator():
            continue
        action.setText(f"{text}\t{shortcut.toString(QtGui.QKeySequence.PortableText)}")
        changed += 1
    return changed


class LayoutRules(QtCore.QObject):
    """What Qt lays out differently on a Mac whatever the style says, put
    back the way it is on Windows and Linux. A message box there has its own
    margins and columns, bold text and a narrower wrap."""

    #: Where shortcuts are spelt out: a Mac. Elsewhere Qt already writes them
    #: in these words.
    SPELL_OUT = sys.platform == 'darwin'

    def eventFilter(self, obj, event):
        if self.SPELL_OUT and isinstance(obj, QtWidgets.QMenu) \
                and event.type() == QtCore.QEvent.Show:
            try:
                spell_out_shortcuts(obj)
            except Exception:
                pass
            return False
        if not isinstance(obj, QtWidgets.QMessageBox):
            return False
        kind = event.type()
        try:
            if kind == QtCore.QEvent.Polish:
                self.lay_out(obj)
            elif kind == QtCore.QEvent.ShowToParent:
                obj.setProperty('_dosidicus_shown', True)
                self.size(obj)
            elif kind == QtCore.QEvent.Hide:
                obj.setProperty('_dosidicus_shown', False)
            elif kind == QtCore.QEvent.Resize and obj.property('_dosidicus_shown'):
                return self.size(obj)
        except Exception:                           # never let a box fail to open
            return False
        return False

    @staticmethod
    def lay_out(box):
        grid = box.layout()
        if not isinstance(grid, QtWidgets.QGridLayout):
            return
        font = QtWidgets.QApplication.font('QMessageBox')
        box.setContentsMargins(0, 0, 0, 0)
        margin = METRICS['PM_DefaultTopLevelMargin']
        spacing = METRICS['PM_DefaultLayoutSpacing']
        grid.setContentsMargins(margin, margin, margin, margin)
        grid.setHorizontalSpacing(spacing)
        grid.setVerticalSpacing(spacing)
        grid.setRowStretch(1, 0)
        grid.setRowMinimumHeight(2, 0)
        fixed = QtWidgets.QSizePolicy.Fixed
        for index in range(grid.count()):
            spacer = grid.itemAt(index).spacerItem()
            if spacer is not None and spacer.sizeHint().height() == 1:
                spacer.changeSize(7 if box.icon() != QtWidgets.QMessageBox.NoIcon else 15,
                                  1, fixed, fixed)
        label = box.findChild(QtWidgets.QLabel, 'qt_msgbox_label')
        if label is not None:
            label.setFont(font)                     # bold on a Mac
        informative = box.findChild(QtWidgets.QLabel, 'qt_msgbox_informativelabel')
        if informative is not None:
            informative.setFont(font)               # small on a Mac
            informative.setContentsMargins(0, 7, 0, 7)
        buttons = box.findChild(QtWidgets.QDialogButtonBox)
        if buttons is not None:
            buttons.setCenterButtons(False)
            index = grid.indexOf(buttons)
            if index >= 0:
                row = grid.getItemPosition(index)[0]
                grid.removeWidget(buttons)
                grid.addWidget(buttons, row, 0, 1, grid.columnCount())

    @staticmethod
    def size(box):
        if box.property('_dosidicus_sizing'):
            return False
        box.setProperty('_dosidicus_sizing', True)
        try:
            size = message_box_size(box)
            changed = size != box.size()
            if changed:
                box.setFixedSize(size)
            QtCore.QCoreApplication.removePostedEvents(box, QtCore.QEvent.LayoutRequest)
            return changed
        finally:
            box.setProperty('_dosidicus_sizing', False)


_pending_titles = []


def keep_message_box_titles():
    """Qt 5 on a Mac drops a message box's title (setWindowTitle does
    nothing there); keep it, as Windows and Linux show it."""
    box = QtWidgets.QMessageBox
    if getattr(box, '_dosidicus_titles_kept', False):
        return
    construct = box.__init__

    def init(self, *args, **kwargs):
        construct(self, *args, **kwargs)
        title = args[1] if len(args) > 1 else None
        if isinstance(title, str) and title:
            QtWidgets.QWidget.setWindowTitle(self, title)

    box.__init__ = init
    box.setWindowTitle = lambda self, title: QtWidgets.QWidget.setWindowTitle(self, title)
    box._dosidicus_titles_kept = True


class MacGameStyle(GameStyle):
    """GameStyle on a Mac, where Fusion would otherwise draw a third larger.

    Fusion scales the sizes written into its code by (the DPI of the text it
    is given) / (the system's base DPI). On a Mac the base is 72 and the
    game's text is at 96, so every such size came out 4/3 as big: a menu 12
    pixels wider than the same menu on Windows. The table in GameStyle covers
    the sizes Fusion can be asked for; the rest are inside its measuring and
    drawing code. So each time Fusion is asked to measure or draw, the text
    measurements it is handed are swapped for the same measurements made at
    72 DPI - the same letters at the same pixel size, so nothing about the
    text changes, and the ratio Fusion multiplies by is 1.
    """

    def __init__(self):
        super().__init__()
        device = QtGui.QImage(1, 1, QtGui.QImage.Format_RGB32)
        per_metre = int(round(72 / 0.0254))
        device.setDotsPerMeterX(per_metre)
        device.setDotsPerMeterY(per_metre)
        self._device = device                # a paint device at 72 DPI
        self._metrics = {}

    def _at_base_dpi(self, option, widget):
        """Swap the option's text measurements for the same ones at 72 DPI."""
        if option is None or widget is None:
            return option
        try:
            font = widget.font()
            dpi = widget.logicalDpiY() or FONT_DPI      # what its text is really at
            key = (font.key(), dpi)
            metrics = self._metrics.get(key)
            if metrics is None:
                same = QtGui.QFont(font)
                if same.pixelSize() <= 0 and same.pointSizeF() > 0:
                    # As many pixels at 72 DPI as it has at the DPI it is drawn at.
                    same.setPointSizeF(same.pointSizeF() * dpi / 72.0)
                metrics = QtGui.QFontMetrics(same, self._device)
                if len(self._metrics) > 256:
                    self._metrics.clear()
                self._metrics[key] = metrics
            option.fontMetrics = metrics
        except Exception:
            pass
        return option

    def sizeFromContents(self, kind, option, size, widget=None):
        return super().sizeFromContents(kind, self._at_base_dpi(option, widget), size, widget)

    def subElementRect(self, element, option, widget=None):
        return super().subElementRect(element, self._at_base_dpi(option, widget), widget)

    def subControlRect(self, control, option, sub, widget=None):
        return super().subControlRect(control, self._at_base_dpi(option, widget), sub, widget)

    def drawControl(self, element, option, painter, widget=None):
        super().drawControl(element, self._at_base_dpi(option, widget), painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        super().drawPrimitive(element, self._at_base_dpi(option, widget), painter, widget)

    def drawComplexControl(self, control, option, painter, widget=None):
        super().drawComplexControl(control, self._at_base_dpi(option, widget), painter, widget)

    def pixelMetric(self, metric, option=None, widget=None):
        fixed = self._metrics_table.get(metric)
        if fixed is not None:
            return fixed
        return QtWidgets.QProxyStyle.pixelMetric(
            self, metric, self._at_base_dpi(option, widget), widget)


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


#: Fonts in src/fonts that this system would not load, and families the game
#: wanted and did not get - for the notes on a screenshot, and for a bug
#: report. Empty when all is well.
FONT_PROBLEMS = []


def load_fonts():
    """Load every font in src/fonts. Returns the families now available.

    A font the system will not load is noted (FONT_PROBLEMS) and the game
    goes on without it: its text then comes from whatever the system has,
    which is not the same picture but is a game that starts. (A font being
    refused must never again stop the game: macOS refused the first emoji
    font outright.)
    """
    del FONT_PROBLEMS[:]
    loaded = set()
    for path in sorted(font_directory().glob('*.ttf')):
        font_id = QtGui.QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            FONT_PROBLEMS.append(f'could not load {path.name}')
            continue
        loaded.update(QtGui.QFontDatabase.applicationFontFamilies(font_id))
    for family in sorted({UI_FONT, MONO_FONT, EMOJI_FONT, LINE_EMOJI_FONT} - loaded):
        FONT_PROBLEMS.append(f'no {family}')
    for problem in FONT_PROBLEMS:
        print(f"[fonts] {problem} - using the system's instead", file=sys.stderr)
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
    rules = getattr(app, '_dosidicus_layout_rules', None)
    if rules is not None:                   # installed before, then undone
        app.removeEventFilter(rules)
    load_fonts()
    # A hard-coded family from older code or a plugin still lands on ours.
    for family in ('Arial', 'Helvetica', 'Verdana', 'Segoe UI', 'Sans Serif', 'sans-serif'):
        QtGui.QFont.insertSubstitution(family, UI_FONT)
    for family in ('Courier New', 'Courier', 'Consolas', 'Menlo', 'monospace', 'Monospace'):
        QtGui.QFont.insertSubstitution(family, MONO_FONT)
    # What a font has no letter for comes from the game's other fonts before
    # any of the system's: arrows and ticks from the monospace, emoji from the
    # game's emoji font. (Qt tries a family's substitutes, in order, for the
    # characters the family lacks.)
    for family, others in ((UI_FONT, [MONO_FONT, EMOJI_FONT]), (MONO_FONT, [EMOJI_FONT])):
        QtGui.QFont.removeSubstitutions(family)         # installing twice adds none twice
        QtGui.QFont.insertSubstitutions(family, others)
    style = MacGameStyle() if sys.platform == 'darwin' else GameStyle()
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
    # A menu opened by itself shows its shortcuts, as one from the menu bar
    # does (a Mac hides them otherwise).
    try:
        app.styleHints().setShowShortcutsInContextMenus(True)
    except AttributeError:
        pass
    if sys.platform == 'darwin':
        keep_message_box_titles()
    app._dosidicus_layout_rules = LayoutRules(app)
    app.installEventFilter(app._dosidicus_layout_rules)
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
        'font_problems': list(FONT_PROBLEMS),
    }


__all__ = ['UI_FONT', 'MONO_FONT', 'EMOJI_FONT', 'LINE_EMOJI_FONT', 'UI_FONT_SIZE', 'prepare_qt', 'install_style',
           'load_fonts', 'ui_font', 'light_palette', 'screen_size', 'reported_size',
           'usable_size',
           'describe', 'GameStyle', 'font_directory']
