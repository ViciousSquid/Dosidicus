"""One look on every system: the game's own font, style and sizes.

src/desktop_style.py makes the game draw itself the same on Windows, macOS
and Linux: Fio UI (src/fonts) for everything, a point that is 1/96 inch
everywhere, Fusion with a fixed light palette, and windows sized from the
screen's size rather than from what a taskbar or dock leaves.
"""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtGui, QtWidgets                          # noqa: E402

from src import desktop_style                                       # noqa: E402

desktop_style.prepare_qt()
_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _installed():
    """Install for one test, and put the application back afterwards: the
    other tests in this run were written against Qt's own defaults."""
    before = (_APP.font(), _APP.palette(), _APP.style().objectName())
    _APP._dosidicus_style = None
    desktop_style.install_style(_APP)
    return before


def _restore(before):
    font, palette, style = before
    rules = getattr(_APP, '_dosidicus_layout_rules', None)
    if rules is not None:
        _APP.removeEventFilter(rules)
        _APP._dosidicus_layout_rules = None
    _APP.setStyle(QtWidgets.QStyleFactory.create(style) or QtWidgets.QStyleFactory.create('Fusion'))
    _APP.setPalette(palette)
    _APP.setFont(font)
    _APP._dosidicus_style = None


def test_the_fonts_ship_with_the_game_under_their_own_names_and_licences():
    folder = desktop_style.font_directory()
    names = {path.name for path in folder.iterdir()}
    assert {'FioUI-Regular.ttf', 'FioUI-Bold.ttf', 'FioUI-Light.ttf', 'FioUI-Semibold.ttf',
            'FioUI-Semilight.ttf', 'IBMPlexMono-Regular.ttf', 'IBMPlexMono-Bold.ttf',
            'Selawik-OFL.txt', 'IBMPlexMono-OFL.txt'} <= names
    assert desktop_style.load_fonts() >= {'Fio UI', 'IBM Plex Mono'}


def test_everything_is_drawn_in_fio_ui_at_one_size():
    before = _installed()
    try:
        seen = desktop_style.describe(_APP)
        assert seen['font_asked'] == seen['font_used'] == 'Fio UI'
        assert seen['font_point_size'] == desktop_style.UI_FONT_SIZE == 10
        assert seen['style'] == 'DosidicusFusion'
        for widget_class in ('QMenu', 'QMenuBar', 'QMessageBox'):
            assert QtWidgets.QApplication.font(widget_class).family() == 'Fio UI'
        assert QtWidgets.QToolTip.font().family() == 'Fio UI'
        # A family written into older code or a plugin still lands on ours.
        for family in ('Arial', 'Verdana'):
            assert QtGui.QFontInfo(QtGui.QFont(family, 12)).family() == 'Fio UI'
        for family in ('Courier New', 'monospace'):
            assert QtGui.QFontInfo(QtGui.QFont(family, 12)).family() == 'IBM Plex Mono'
    finally:
        _restore(before)


def test_a_point_is_the_same_number_of_pixels_on_every_system():
    """In a process of its own, as the game starts: prepared before the
    application exists, a point is 1/96 inch whatever the system says."""
    import json
    import subprocess
    script = ("import json, sys; sys.path.insert(0, %r);"
              "from PyQt5 import QtWidgets; from src import desktop_style as d;"
              "assert d.prepare_qt(); app = QtWidgets.QApplication([]);"
              "d.install_style(app); print(json.dumps(d.describe(app)))" % str(ROOT))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    env.pop('QT_FONT_DPI', None)
    out = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True,
                         text=True, timeout=120, check=True).stdout
    seen = json.loads(out.strip().splitlines()[-1])
    assert seen['logical_dpi'] == 96
    assert seen['font_pixel_size'] == 13                     # 10 pt at 96 to the inch
    assert seen['font_used'] == 'Fio UI' and seen['style'] == 'DosidicusFusion'


def test_the_game_is_light_whatever_the_system_theme():
    before = _installed()
    try:
        dark = QtGui.QPalette()
        dark.setColor(QtGui.QPalette.Window, QtGui.QColor('#202020'))
        _APP.setPalette(dark)
        _APP._dosidicus_style = None
        desktop_style.install_style(_APP)
        palette = _APP.palette()
        assert palette.color(QtGui.QPalette.Window).name() == '#efefef'
        assert palette.color(QtGui.QPalette.Text).name() == '#000000'
        assert palette.color(QtGui.QPalette.Base).name() == '#ffffff'
    finally:
        _restore(before)


def test_dialog_buttons_keep_one_order_on_every_system():
    before = _installed()
    try:
        style = _APP.style()
        assert (style.styleHint(QtWidgets.QStyle.SH_DialogButtonLayout)
                == QtWidgets.QDialogButtonBox.WinLayout)
        assert style.styleHint(QtWidgets.QStyle.SH_ScrollBar_Transient) == 0
        # Anything not fixed is still Fusion's own answer.
        assert style.pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent) > 0
    finally:
        _restore(before)


def test_installing_twice_changes_nothing_and_preparing_late_does_nothing():
    before = _installed()
    try:
        assert desktop_style.install_style(_APP) is False
        assert desktop_style.prepare_qt() is False           # the application exists
    finally:
        _restore(before)


def test_a_window_that_fills_the_screen_is_the_same_size_on_every_system():
    screen = _APP.primaryScreen()
    width, height, _ratio = desktop_style.screen_size(screen)
    assert desktop_style.usable_size(screen) == (width, height - desktop_style.SYSTEM_CHROME)
    os.environ[desktop_style.SCREEN_OVERRIDE] = '1920x1080'
    try:
        assert desktop_style.screen_size(screen) == (1920, 1080, 1.0)
        assert desktop_style.usable_size(screen) == (1920, 920)
        from src.display_scaling import DisplayScaling
        assert DisplayScaling.screen_pixels(screen) == (1920, 1080)
    finally:
        del os.environ[desktop_style.SCREEN_OVERRIDE]
    os.environ[desktop_style.SCREEN_OVERRIDE] = 'nonsense'
    try:
        assert desktop_style.screen_size(screen)[:2] == (width, height)
    finally:
        del os.environ[desktop_style.SCREEN_OVERRIDE]


def test_no_window_is_sized_from_what_the_systems_bars_leave():
    """availableGeometry differs with every taskbar and dock; it may place a
    window, never size one."""
    sizing = re.compile(r'availableGeometry\(\)\.(width|height)\(\)|avail\.(width|height)\(\)')
    for name in ('brain_tool.py', 'designer_window.py', 'display_scaling.py', 'ui.py'):
        text = (ROOT / 'src' / name).read_text(encoding='utf-8')
        assert not sizing.search(text), name


def test_every_window_is_placed_in_the_same_spot_on_every_system():
    """Each system keeps a different strip of the screen for itself and
    reports what is left. Placed from that, the same window landed somewhere
    different on each. The game places its windows from one rectangle that is
    the same everywhere for the same screen."""
    screen = _APP.primaryScreen()
    os.environ[desktop_style.SCREEN_OVERRIDE] = '1920x1080'
    try:
        area = desktop_style.layout_area(screen)
        assert (area.left(), area.top(), area.width(), area.height()) == (0, 40, 1920, 952)
        assert area.top() == desktop_style.TOP_INSET            # below any menu bar or panel
        assert 1080 - (area.top() + area.height()) == 88        # above a Mac's Dock (78)
        # A window that fills the height, title bar and all, ends above the Dock.
        tallest = desktop_style.usable_size(screen)[1]
        assert area.top() + desktop_style.TITLE_BAR + tallest == 1080 - 88
    finally:
        del os.environ[desktop_style.SCREEN_OVERRIDE]
    # Nothing that places a window asks the system what it has left free.
    for name in ('main.py', 'src/brain_tool.py', 'src/statistics_window.py',
                 'src/preferences.py', 'src/language_splash.py', 'src/brain_neuron_outputs.py'):
        text = (ROOT / name).read_text(encoding='utf-8')
        assert 'availableGeometry' not in text, name
        assert 'layout_area' in text, name
    # Statistics no longer sits at 0, 0, where a Mac moved it and the others did not.
    assert 'self.move(0, 0)' not in (ROOT / 'src' / 'statistics_window.py').read_text()


def test_no_other_font_family_is_written_into_the_game():
    family = re.compile(r"""QFont\(\s*["'](Arial|Verdana|Helvetica|Courier New|Consolas|Segoe UI)["']"""
                        r"""|font-family:\s*(Arial|sans-serif|monospace|'Consolas'|'Times)""")
    offenders = []
    for folder in ('src', 'plugins'):
        for path in (ROOT / folder).rglob('*.py'):
            if path.name == 'desktop_style.py':
                continue
            if family.search(path.read_text(encoding='utf-8')):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, offenders


def test_both_ways_into_the_game_set_the_style_before_any_window():
    text = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert text.count('prepare_qt()') == 2 and text.count('install_style(') == 2
    for match in re.finditer(r'QtWidgets\.QApplication\(sys\.argv\)', text):
        before = text[:match.start()]
        assert before.rfind('prepare_qt()') > before.rfind('def ')


def test_fusions_sizes_are_written_out_as_it_gives_them_at_96_dpi():
    """A Mac multiplies Fusion's sizes by 96/72. The table the game uses
    instead must be exactly what Fusion gives where nothing is multiplied -
    here, on Linux at 96 DPI (run in a process of its own, prepared as the
    game prepares)."""
    if sys.platform == 'darwin':
        return
    import json
    import subprocess
    script = ("import json, sys; sys.path.insert(0, %r);"
              "from PyQt5 import QtWidgets; from src import desktop_style as d;"
              "d.prepare_qt(); app = QtWidgets.QApplication([]);"
              "f = QtWidgets.QStyleFactory.create('Fusion'); S = QtWidgets.QStyle;"
              "print(json.dumps({n: f.pixelMetric(getattr(S, n)) for n in d.METRICS}))" % str(ROOT))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    out = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True,
                         text=True, timeout=120, check=True).stdout
    assert json.loads(out.strip().splitlines()[-1]) == desktop_style.METRICS


def test_a_message_box_is_laid_out_and_sized_the_same_way_everywhere():
    before = _installed()
    try:
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, 'Dosidicus',
                                    'Let the squid go out to other tanks?',
                                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        box.setInformativeText('What happens to it out there cannot be undone.')
        box.show()
        _APP.processEvents()
        grid = box.layout()
        assert grid.contentsMargins().left() == grid.contentsMargins().top() == 11
        assert grid.horizontalSpacing() == grid.verticalSpacing() == 6
        label = box.findChild(QtWidgets.QLabel, 'qt_msgbox_label')
        assert not label.font().bold() and label.font().family() == 'Fio UI'
        buttons = box.findChild(QtWidgets.QDialogButtonBox)
        position = grid.getItemPosition(grid.indexOf(buttons))
        assert position[1] == 0 and position[3] == grid.columnCount()     # under everything
        assert box.size() == desktop_style.message_box_size(box)
        # Qt's own built-in picture, not the system's.
        icon = _APP.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxQuestion)
        assert not icon.isNull()
        box.close()
    finally:
        _restore(before)


def test_one_text_engine_is_asked_for_on_windows_and_a_mac():
    text = (ROOT / 'src' / 'desktop_style.py').read_text(encoding='utf-8')
    assert "fontengine=freetype" in text and "DOSIDICUS_NATIVE_TEXT" in text


def test_every_emoji_the_game_uses_is_in_its_own_emoji_font():
    """Each system has its own emoji font. The game carries the emoji it
    uses (tools/subset_emoji_font.py), so they are the same picture
    everywhere. An emoji added to the game and not to the font would be drawn
    by whatever the system has: run the tool again."""
    from tools.subset_emoji_font import FAMILY, OUTPUT, emoji_in_the_game
    assert FAMILY == desktop_style.EMOJI_FONT and OUTPUT.is_file()
    assert OUTPUT.stat().st_size < 2_000_000                  # a subset, not all of Noto
    font = QtGui.QRawFont(str(OUTPUT), 16)
    assert font.isValid() and font.familyName() == 'Dosidicus Emoji'
    used = emoji_in_the_game()
    assert len(used) > 100
    missing = sorted(ch for ch in used if not font.supportsCharacter(ord(ch)))
    # Symbols Noto Color Emoji does not draw at all are text, not emoji.
    full_lacks = {ch for ch in missing if ord(ch) < 0x1F000}
    assert not [ch for ch in missing if ch not in full_lacks], \
        'not in src/fonts/DosidicusEmoji.ttf - run tools/subset_emoji_font.py: ' + ' '.join(missing)
    assert (desktop_style.font_directory() / 'DosidicusEmoji-OFL.txt').is_file()
    # The same emoji as black-and-white line drawings.
    from tools.subset_emoji_font import LINE_FAMILY, LINE_OUTPUT
    line = QtGui.QRawFont(str(LINE_OUTPUT), 16)
    assert line.isValid() and line.familyName() == LINE_FAMILY == desktop_style.LINE_EMOJI_FONT
    assert not [ch for ch in used if ord(ch) >= 0x1F000 and not line.supportsCharacter(ord(ch))]
    assert (desktop_style.font_directory() / 'DosidicusLineEmoji-OFL.txt').is_file()


def test_the_brain_designer_button_is_a_plain_black_and_white_brain():
    text = (ROOT / 'src' / 'brain_network_tab.py').read_text(encoding='utf-8')
    start = text.index('self.new_50x50_button = QtWidgets.QPushButton("\U0001F9E0")')
    style = text[start:text.index('QPushButton:hover', start)]
    assert 'font-family: "Dosidicus Line Emoji"' in style and 'color: #000000' in style
    # Drawn from the line font it is one colour: every painted pixel is a grey.
    font = QtGui.QRawFont(str(desktop_style.font_directory() / 'DosidicusLineEmoji.ttf'), 40)
    image = font.alphaMapForGlyph(font.glyphIndexesForString('\U0001F9E0')[0])
    assert not image.isNull() and image.width() > 20
    # Checked pixel by pixel: QImage.isGrayscale() answers False for an
    # alpha-only image, which is what some Qt builds return here.
    colours = {image.pixelColor(x, y).getRgb()[:3] for y in range(image.height())
               for x in range(image.width())}
    assert all(red == green == blue for red, green, blue in colours)


def test_what_fio_ui_lacks_comes_from_the_games_other_fonts_first():
    before = _installed()
    try:
        assert QtGui.QFont.substitutes('Fio UI') == ['ibm plex mono', 'dosidicus emoji']
        assert QtGui.QFont.substitutes('IBM Plex Mono') == ['dosidicus emoji']
        desktop_style.install_style(_APP)               # again: nothing is added twice
        assert len(QtGui.QFont.substitutes('Fio UI')) == 2
        assert 'Dosidicus Emoji' in desktop_style.load_fonts()
    finally:
        _restore(before)
        QtGui.QFont.removeSubstitutions('Fio UI')
        QtGui.QFont.removeSubstitutions('IBM Plex Mono')


def test_a_font_the_system_refuses_does_not_stop_the_game(monkeypatch):
    """macOS would not load the first emoji font, and the game did not start.
    A refused font is noted and the game goes on with the rest."""
    real = QtGui.QFontDatabase.addApplicationFont

    def refuse_emoji(path):
        return -1 if 'DosidicusEmoji' in str(path) else real(path)
    monkeypatch.setattr(QtGui.QFontDatabase, 'addApplicationFont', staticmethod(refuse_emoji))
    loaded = desktop_style.load_fonts()                      # no exception
    assert 'Fio UI' in loaded and 'Dosidicus Emoji' not in loaded
    assert desktop_style.FONT_PROBLEMS == ['could not load DosidicusEmoji.ttf',
                                           'no Dosidicus Emoji']
    monkeypatch.undo()
    assert 'Dosidicus Emoji' in desktop_style.load_fonts()
    assert desktop_style.FONT_PROBLEMS == []


def test_the_colour_emoji_font_has_outlines_for_the_systems_that_insist_on_them():
    """macOS will not load a font with no outline table. The colour emoji are
    pictures, so they are given an empty outline each: an ordinary TrueType
    font to the system, the same pictures to FreeType, which draws them."""
    data = (desktop_style.font_directory() / 'DosidicusEmoji.ttf').read_bytes()
    count = int.from_bytes(data[4:6], 'big')
    tables = {data[12 + 16 * i:16 + 16 * i].decode('latin-1') for i in range(count)}
    assert {'glyf', 'loca', 'CBDT', 'CBLC', 'cmap'} <= tables


def test_a_menu_names_its_shortcuts_in_the_same_words_on_every_system():
    """A Mac writes shortcuts as symbols, and swaps Ctrl with Command. The
    game spells them out there ("Ctrl+Shift+B") and leaves the keys unswapped,
    so the menu is the same menu and what it says is the key that works."""
    menu = QtWidgets.QMenu()
    designer = menu.addAction('Brain Designer')
    designer.setShortcut(QtGui.QKeySequence('Ctrl+Shift+B'))
    plain = menu.addAction('Statistics')
    menu.addSeparator()
    already = menu.addAction('preferences\tCtrl+P')
    already.setShortcut(QtGui.QKeySequence('Ctrl+P'))
    assert desktop_style.spell_out_shortcuts(menu) == 1
    assert designer.text() == 'Brain Designer\tCtrl+Shift+B'
    assert plain.text() == 'Statistics' and already.text() == 'preferences\tCtrl+P'
    assert desktop_style.spell_out_shortcuts(menu) == 0          # nothing is added twice
    assert designer.shortcut() == QtGui.QKeySequence('Ctrl+Shift+B')   # the key is unchanged
    text = (ROOT / 'src' / 'desktop_style.py').read_text(encoding='utf-8')
    assert 'AA_MacDontSwapCtrlAndMeta, True' in text
    assert desktop_style.LayoutRules.SPELL_OUT == (sys.platform == 'darwin')


def test_on_a_mac_fusion_is_handed_text_measured_at_its_own_base_dpi():
    """Fusion multiplies the sizes inside its code by text DPI / 72 on a Mac.
    The Mac style hands it the same text measured at 72, so the ratio is 1.
    Run here against the real Fusion: what it measures and draws must come
    out exactly as it does without the swap, since here the ratio is 1 anyway
    - the swap must change nothing but the DPI it is measured at."""
    before = _installed()
    try:
        mac, plain = desktop_style.MacGameStyle(), desktop_style.GameStyle()
        _APP._mac_style_for_test = (mac, plain)
        button = QtWidgets.QPushButton('Load a custom brain')
        option = QtWidgets.QStyleOptionButton()
        option.initFrom(button)
        option.text = button.text()
        real = QtGui.QFontMetrics(button.font())
        swapped = mac._at_base_dpi(option, button).fontMetrics
        assert swapped.fontDpi() == 72                       # what Fusion divides by 72
        # ...and the same letters at the same size, to the pixel.
        for text in ('Load a custom brain', 'Ctrl+Shift+B', 'Functional Neurons: 0'):
            assert swapped.horizontalAdvance(text) == real.horizontalAdvance(text)
        assert (swapped.height(), swapped.ascent()) == (real.height(), real.ascent())
        assert mac._at_base_dpi(None, button) is None and mac._at_base_dpi(option, None) is option
        assert mac.pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent) == 14
        size = QtCore.QSize(real.horizontalAdvance(option.text), real.height())
        kind = QtWidgets.QStyle.CT_PushButton
        other = QtWidgets.QStyleOptionButton(option)
        other.fontMetrics = real
        assert mac.sizeFromContents(kind, option, size, button) \
            == plain.sizeFromContents(kind, other, size, button)
    finally:
        _restore(before)


def test_the_aquarium_opens_at_the_top_left_and_on_top_for_five_seconds():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'self._opens_at = (area.left(), area.top())' in main          # the top left corner
    assert 'self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)' in main
    assert 'ON_TOP_SECONDS = 5.0' in main
    assert 'self._on_top_timer.start(int(self.ON_TOP_SECONDS * 1000))' in main
    assert "area.center().x() - (self.geometry().width() // 2) - 300" not in main
    # What happens when the five seconds are up, on a real window.
    import ast
    tree = ast.parse(main)
    source = next(ast.get_source_segment(main, node) for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == 'stop_staying_on_top')
    scope = {'QtCore': QtCore}
    exec('import textwrap\n', scope)
    import textwrap
    exec(textwrap.dedent(source), scope)

    class Tank(QtWidgets.QMainWindow):
        stop_staying_on_top = scope['stop_staying_on_top']

    tank = Tank()
    tank.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
    tank.move(0, 40)
    tank.show()
    assert tank.windowFlags() & QtCore.Qt.WindowStaysOnTopHint          # above the others...
    tank.stop_staying_on_top()                                           # ...for five seconds
    assert not tank.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    assert tank.isVisible() and (tank.pos().x(), tank.pos().y()) == (0, 40)   # still there
    tank.stop_staying_on_top()                                           # twice does no harm
    assert tank.isVisible()
    tank.close()
    # Statistics opens beside the aquarium, not on top of it.
    stats = (ROOT / 'src' / 'statistics_window.py').read_text(encoding='utf-8')
    assert 'area.left() + DisplayScaling.window_size()[0] + 24, area.top()' in stats


def test_a_window_the_system_shifts_is_put_back_where_it_was_meant_to_go():
    """Windows put the Brain Tool 7 pixels to the right of where it was asked
    to be - once, before it had a frame. Asked again it goes exactly there,
    so the first correction is to ask again; only a window shifted every time
    is asked for a place that much the other way."""
    class Window(QtWidgets.QWidget):
        def __init__(self, shifts):
            super().__init__()
            self.asked, self.shifts = [], list(shifts)

        def move(self, x, y):
            self.asked.append((x, y))
            shift = self.shifts.pop(0) if self.shifts else 0
            self._at = (x + shift, y)

        def pos(self):
            return QtCore.QPoint(*self._at)

        def isVisible(self):
            return True

    def look(window):
        window._placement_check.stop()
        window._placement_check.timeout.emit()

    # Shifted once, as Windows did: asking again is enough.
    window = Window(shifts=[7])
    desktop_style.place_exactly(window, 519, 40)
    assert window.pos().x() == 526
    look(window)
    assert window.asked == [(519, 40), (519, 40)] and window.pos().x() == 519
    look(window)                                                    # the second look: nothing to do
    assert window.asked == [(519, 40), (519, 40)]
    window._placement_check.stop()

    # Shifted every time: then, and only then, lean against it.
    window = Window(shifts=[7, 7, 7])
    desktop_style.place_exactly(window, 519, 40)
    look(window)
    look(window)
    assert window.asked == [(519, 40), (519, 40), (512, 40)]
    assert (window.pos().x(), window.pos().y()) == (519, 40)
    window._placement_check.stop()

    # Put where it was asked: left alone.
    window = Window(shifts=[])
    desktop_style.place_exactly(window, 0, 40)
    look(window)
    assert window.asked == [(0, 40)]
    window._placement_check.stop()
