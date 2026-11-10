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

from PyQt5 import QtGui, QtWidgets                                  # noqa: E402

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
        assert desktop_style.usable_size(screen) == (1920, 980)
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
