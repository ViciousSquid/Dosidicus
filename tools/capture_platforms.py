#!/usr/bin/env python3
"""Photograph the running game, so the same picture can be taken on every system.

Starts the real game (main.py's MainWindow, a new squid, the game's own font
and style), lets it run, and saves:

  shots/main.png         the tank window
  shots/brain-*.png      the Brain Tool on several of its tabs
  shots/statistics.png   the floating statistics window
  shots/journey.png      View > Journey
  shots/splash.png       the language splash
  shots/message.png      a message box
  shots/menu.png         the main window with a menu open
  screen.png             the whole screen, with the system's own window frames
                         (where the system lets a program look at the screen)
  layout.json            where every widget of every window is, and the text
                         measurements - what `--compare` checks across systems
  notes.json             the system, Qt, the screen, the font actually used

Each window is saved from the window itself (QWidget.grab), so the picture is
what the game drew, the same way everywhere, without the system's title bar -
that is the system's, and screen.png shows it.

  python tools/capture_platforms.py OUTPUT_DIR [--label windows]
  python tools/capture_platforms.py --compare DIR_A DIR_B [DIR_C ...]

DOSIDICUS_SCREEN=1920x1080 lays the game out for that screen whatever the
machine has, so machines with different screens take the same picture.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
BRAIN_TABS = 8          # at most this many tabs of the Brain Tool
RUN_SECONDS = 26.0      # the game runs this long before the first picture


def _layout(widget):
    """Every visible widget of a window: class, name and place in the window."""
    from PyQt5 import QtCore, QtWidgets
    found = []
    for child in [widget] + widget.findChildren(QtWidgets.QWidget):
        if not child.isVisibleTo(widget) and child is not widget:
            continue
        if child.window() is not widget.window():
            continue
        top = child.mapTo(widget, QtCore.QPoint(0, 0)) if child is not widget else QtCore.QPoint(0, 0)
        found.append({'class': type(child).__name__, 'name': child.objectName(),
                      'x': top.x(), 'y': top.y(),
                      'w': child.width(), 'h': child.height()})
    return found


def capture(output, label, brain_size=None):
    from test_lan_round_trip import _setup, _shutdown
    output = output.resolve()
    shots = output / 'shots'
    shots.mkdir(parents=True, exist_ok=True)
    random.seed(20260311)
    try:
        import numpy
        numpy.random.seed(20260311)
    except ImportError:
        pass
    app, main = _setup(output / 'game')
    from PyQt5 import QtCore, QtGui, QtWidgets
    from src import desktop_style
    from src.personality import Personality

    notes = {'label': label, 'system': platform.platform(), 'python': platform.python_version(),
             'qt': QtCore.QT_VERSION_STR, 'pyqt': QtCore.PYQT_VERSION_STR,
             'session': os.environ.get('XDG_SESSION_TYPE', ''),
             'style': desktop_style.describe(app), 'shots': {}, 'problems': []}
    layout = {'text': {}, 'windows': {}}
    for size in (8, 10, 12, 14, 18, 24):
        for family in (desktop_style.UI_FONT, desktop_style.MONO_FONT):
            metrics = QtGui.QFontMetrics(desktop_style.ui_font(size, family=family))
            layout['text'][f'{family} {size}'] = {
                'line': metrics.height(), 'ascent': metrics.ascent(),
                'width': metrics.horizontalAdvance('Hunger 42  Anxiety 17  can_see_plant')}

    def drawn_by(family, text):
        """The fonts that actually draw `text` when `family` is asked for."""
        font = QtGui.QFont(family, 14)
        text_layout = QtGui.QTextLayout(text, font)
        text_layout.beginLayout()
        text_layout.createLine()
        text_layout.endLayout()
        return [run.rawFont().familyName() for run in text_layout.glyphRuns()]

    database = QtGui.QFontDatabase()
    known = set(database.families())
    notes['fonts'] = {}
    for family in (desktop_style.UI_FONT, desktop_style.MONO_FONT,
                   desktop_style.EMOJI_FONT, desktop_style.LINE_EMOJI_FONT):
        info = QtGui.QFontInfo(QtGui.QFont(family, 14))
        notes['fonts'][family] = {
            'listed': family in known, 'resolves_to': info.family(),
            'exact': info.exactMatch(),
            'brain_drawn_by': drawn_by(family, '\U0001F9E0'),
            'arrow_drawn_by': drawn_by(family, '\u21ba'),
            'letter_drawn_by': drawn_by(family, 'A')}
    notes['problems'].extend(desktop_style.FONT_PROBLEMS)
    notes['font_substitutes'] = {family: QtGui.QFont.substitutes(family)
                                 for family in (desktop_style.UI_FONT, desktop_style.MONO_FONT)}

    def save(name, widget):
        image = widget.grab()
        image.save(str(shots / f'{name}.png'))
        notes['shots'][name] = [image.width(), image.height()]
        layout['windows'][name] = _layout(widget)

    def write():
        (output / 'notes.json').write_text(json.dumps(notes, indent=2))
        (output / 'layout.json').write_text(json.dumps(layout, indent=1))

    # The splash first: it is what a player sees first.
    try:
        from src.language_splash import LanguageSplash, available_languages
        splash = LanguageSplash(available_languages(), 'en')
        splash.show()
        app.processEvents()
        save('splash', splash)
        splash.close()
        splash.deleteLater()
    except Exception as exc:                        # noqa: BLE001 - noted, not fatal
        notes['problems'].append(f'splash: {exc!r}')

    window = main.MainWindow(specified_personality=Personality.ADVENTUROUS)
    window.show()
    started = time.monotonic()
    state = {'step': 0, 'tab': 0, 'waited': None}
    timer = QtCore.QTimer()
    ui = window.user_interface

    def wait(seconds):
        """True once `seconds` have passed in the current step."""
        now = time.monotonic()
        if state['waited'] is None:
            state['waited'] = now
        if now - state['waited'] >= seconds:
            state['waited'] = None
            return True
        return False

    def whole_screen():
        target = str(output / 'screen.png')
        try:
            if sys.platform == 'darwin':
                subprocess.run(['screencapture', '-x', target], timeout=30, check=False)
            elif app.platformName() in ('windows', 'xcb'):
                app.primaryScreen().grabWindow(0).save(target)
            elif app.platformName().startswith('wayland'):
                # A Wayland program cannot look at the screen; the compositor's
                # own screenshot tool can (weston, started with --debug).
                before = set(output.glob('wayland-screenshot-*.png'))
                subprocess.run(['weston-screenshooter'], cwd=str(output), timeout=30,
                               check=False)
                taken = sorted(set(output.glob('wayland-screenshot-*.png')) - before)
                if taken:
                    taken[-1].replace(target)
        except Exception as exc:                    # noqa: BLE001
            notes['problems'].append(f'screen: {exc!r}')
        notes['screen_captured'] = os.path.exists(target)

    def tick():
        try:
            step()
        except Exception as exc:                    # noqa: BLE001
            import traceback
            notes['problems'].append(f'step {state["step"]}: {exc!r}')
            traceback.print_exc()
            state['step'] += 1
            state['waited'] = None

    def step():
        brain_window = window.brain_window
        number = state['step']
        if number == 0:                             # let the squid hatch and live a little
            running = time.monotonic() - started
            on_top = bool(window.windowFlags() & QtCore.Qt.WindowStaysOnTopHint)
            if running >= 2.0 and 'tank_on_top_after_2s' not in notes:
                notes['tank_on_top_after_2s'] = on_top
            if running >= 9.0 and 'tank_on_top_after_9s' not in notes:
                notes['tank_on_top_after_9s'] = on_top
            if running >= RUN_SECONDS:
                state['step'] = 1
        elif number == 1:
            # The windows a player gets, opened by the game itself and left
            # exactly where it puts them: the tank, the Brain Tool and the
            # decorations (MainWindow.open_initial_windows), and Statistics.
            window.open_initial_windows()
            if ui.statistics_window is None or not ui.statistics_window.isVisible():
                ui.toggle_statistics_window()
            state['step'] = 1.5
        elif number == 1.5 and wait(4.0):
            placed = {'tank': window, 'brain_tool': brain_window,
                      'statistics': ui.statistics_window,
                      'decorations': getattr(ui, 'decoration_window', None)}
            notes['layout'] = {
                name: [shown.pos().x(), shown.pos().y(), shown.width(), shown.height()]
                for name, shown in placed.items() if shown is not None and shown.isVisible()}
            whole_screen()                          # the layout, as the game made it
            if brain_size:                          # a size every runner's screen can hold
                brain_window.resize(*brain_size)
                notes['brain_resized_to'] = list(brain_size)
            journey = getattr(ui, 'journey_window', None)
            if journey is None or not journey.isVisible():
                ui.toggle_journey_window()
            state['step'] = 2
        elif number == 2 and wait(4.0):
            save('main', window)
            save('statistics', ui.statistics_window)
            save('journey', ui.journey_window)
            notes['window_sizes'] = {
                'main': [window.width(), window.height()],
                'brain': [brain_window.width(), brain_window.height()],
                'statistics': [ui.statistics_window.width(), ui.statistics_window.height()],
                'journey': [ui.journey_window.width(), ui.journey_window.height()]}
            state['step'] = 3
        elif number == 3:                           # the Brain Tool, tab by tab
            tabs = brain_window.tabs
            index = state['tab']
            if index >= min(tabs.count(), BRAIN_TABS):
                tabs.setCurrentIndex(0)
                state['step'] = 4
                return
            if tabs.currentIndex() != index:
                tabs.setCurrentIndex(index)
                state['waited'] = None
            if wait(2.5):
                save(f'brain-{index + 1}', brain_window)
                notes.setdefault('brain_tabs', []).append(tabs.tabText(index))
                state['tab'] += 1
        elif number == 4:                           # a message box, as the game shows them
            box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, 'Dosidicus',
                                        'Let the squid go out to other tanks?',
                                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                        window)
            box.setInformativeText('What happens to it out there cannot be undone.')
            box.show()
            state['box'] = box
            state['step'] = 5
        elif number == 5 and wait(1.5):
            save('message', state['box'])
            state['box'].close()
            state['step'] = 6
        elif number == 6:                           # a menu, open
            bar = window.menuBar()
            actions = [action for action in bar.actions() if action.menu() is not None]
            if actions:
                menu = actions[min(1, len(actions) - 1)].menu()
                menu.popup(bar.mapToGlobal(QtCore.QPoint(0, bar.height())))
                state['menu'] = menu
            state['step'] = 7
        elif number == 7 and wait(1.5):
            menu = state.get('menu')
            if menu is not None:
                save('menu', menu)
                menu.close()
            state['step'] = 8
        elif number == 8:
            squid = window.squid
            notes['squid'] = {'hunger': round(squid.hunger), 'anxiety': round(squid.anxiety),
                              'happiness': round(squid.happiness),
                              'neurons': len(brain_window.brain_widget.neuron_positions)}
            # How big the squid is drawn, and in how big a tank: what has to
            # be the same on every system for the same screen.
            from src.display_scaling import DisplayScaling
            notes['scale'] = {
                'tank_scale': round(DisplayScaling.tank_scale(), 4),
                'squid': [int(squid.squid_width), int(squid.squid_height)],
                'tank_window': [window.width(), window.height()],
                'squid_share_of_width': round(squid.squid_width / max(1, window.width()), 4),
                'food': DisplayScaling.points(64)}
            notes['seconds'] = round(time.monotonic() - started, 1)
            write()
            state['step'] = 9
            _shutdown(app, window, timer, None, 0)
        if time.monotonic() - started > 240:
            notes['problems'].append('ran out of time')
            write()
            _shutdown(app, window, timer, None, 1)

    timer.timeout.connect(tick)
    timer.start(250)
    code = app.exec_()
    write()
    print(json.dumps({'label': label, 'shots': sorted(notes['shots']),
                      'style': notes['style'], 'problems': notes['problems']}, indent=1))
    return code


#: Windows whose widgets are the same from one run to the next. The other
#: Brain Tool tabs list what this particular squid has learned and remembered,
#: so their contents (and the widgets holding them) differ between any two runs.
FIXED_WINDOWS = ('splash', 'main', 'statistics', 'message', 'menu', 'brain-1')


def compare(folders, report=None):
    """Compare what each system drew. Text measurements, window sizes and the
    place of every widget in the fixed windows must agree exactly; the
    pictures are compared pixel by pixel and the share that differs reported
    (each system smooths the edges of letters its own way, and no two runs of
    a living squid are the same)."""
    runs = []
    for folder in folders:
        notes = json.loads((folder / 'notes.json').read_text())
        layout = json.loads((folder / 'layout.json').read_text())
        runs.append((notes['label'], folder, notes, layout))
    first_label, first_folder, first_notes, first_layout = runs[0]
    lines = [f'# The same game on {len(runs)} systems', '',
             '| System | Qt platform | Screen | Font used | 10 pt in pixels | Line height |',
             '|---|---|---|---|---|---|']
    for label, _folder, notes, _layout_ in runs:
        style = notes['style']
        screen = 'x'.join(str(v) for v in (style['screen_assumed'] or style['screen']))
        lines.append(f"| {label} | {style['platform']} | {screen} | {style['font_used']} | "
                     f"{style['font_pixel_size']} | {style['line_height']} |")
    lines += ['', f'Compared with **{first_label}**:', '',
              '| System | Text measurements | Window sizes | Widgets in the same place '
              '(fixed windows) | Pixels that differ |', '|---|---|---|---|---|']
    try:
        import numpy
        from PIL import Image, ImageChops
    except ImportError:
        Image = None
    agree = True
    details = []
    for label, folder, notes, layout in runs[1:]:
        text_same = layout['text'] == first_layout['text']
        sizes_same = notes['shots'] == first_notes['shots']
        same = total = 0
        for name in FIXED_WINDOWS:
            widgets = first_layout['windows'].get(name, [])
            others = layout['windows'].get(name, [])
            total += max(len(widgets), len(others))
            for index, widget in enumerate(widgets):
                if index < len(others) and others[index] == widget:
                    same += 1
                elif len(details) < 24:
                    other = others[index] if index < len(others) else None
                    details.append(f'- {label} / {name}: `{widget}` on {first_label}, '
                                   f'`{other}` on {label}')
        pixels = []
        if Image is not None:
            for name in sorted(first_notes['shots']):
                a, b = first_folder / 'shots' / f'{name}.png', folder / 'shots' / f'{name}.png'
                if not (a.exists() and b.exists()):
                    continue
                first, second = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
                if first.size != second.size:
                    pixels.append(f'{name}: sizes differ')
                    continue
                difference = numpy.asarray(ImageChops.difference(first, second).convert('L'))
                pixels.append(f'{name} {100.0 * float((difference > 24).mean()):.1f}%')
        placed_same = notes.get('layout') == first_notes.get('layout')
        if not text_same or not sizes_same or same != total or not placed_same:
            agree = False
        if not placed_same:
            for name in sorted(set(first_notes.get('layout') or {}) | set(notes.get('layout') or {})):
                here = (first_notes.get('layout') or {}).get(name)
                there = (notes.get('layout') or {}).get(name)
                if here != there:
                    details.append(f'- {label} / where the {name} window is put: {here} on '
                                   f'{first_label}, {there} on {label}')
        if not sizes_same:
            for name in sorted(set(first_notes['shots']) | set(notes['shots'])):
                here, there = first_notes['shots'].get(name), notes['shots'].get(name)
                if here != there:
                    details.append(f'- {label} / {name}: {here} on {first_label}, '
                                   f'{there} on {label}')
        lines.append(f"| {label} | {'identical' if text_same else 'DIFFERENT'} | "
                     f"{'identical' if sizes_same else 'DIFFERENT'} | {same} of {total} | "
                     f"{', '.join(pixels) or 'not compared'} |")
    if details:
        lines += ['', 'Not the same:', ''] + details
    lines += ['', 'Fixed windows: ' + ', '.join(FIXED_WINDOWS) + '. The other Brain Tool tabs '
              "list what one particular squid has learned, so their contents differ between "
              'any two runs.', '',
              'Pixels differ where the game itself differs between two runs (where the '
              'squid is, what it is thinking, the numbers) and at the edges of letters, '
              'which each system smooths in its own way.']
    text = '\n'.join(lines) + '\n'
    if report:
        report.write_text(text)
    print(text)
    return 0 if agree else 1


#: The pictures kept in the repository (the rest stay in the run's artifacts).
KEPT = (('main', 'The tank'), ('brain-1', 'Brain Tool: the network'),
        ('brain-2', 'Brain Tool: learning'), ('statistics', 'Statistics'),
        ('journey', 'Journey'), ('splash', 'Language splash'),
        ('message', 'A message box'), ('menu', 'A menu'))


def publish(folders, target):
    """Copy the kept pictures of every system into `target` and write its
    README: the comparison, then the pictures side by side."""
    import shutil
    folders = [folder for folder in folders if (folder / 'notes.json').exists()]
    if not folders:
        print('nothing was captured')
        return 1
    target.mkdir(parents=True, exist_ok=True)
    report = target / 'README.md'
    compare(folders, report)
    labels = []
    for folder in folders:
        notes = json.loads((folder / 'notes.json').read_text())
        label = notes['label']
        labels.append((label, notes))
        place = target / label
        if place.exists():
            shutil.rmtree(place)
        place.mkdir(parents=True)
        for name, _title in KEPT:
            if (folder / 'shots' / f'{name}.png').exists():
                shutil.copyfile(folder / 'shots' / f'{name}.png', place / f'{name}.png')
        if (folder / 'screen.png').exists():
            shutil.copyfile(folder / 'screen.png', place / 'screen.png')
        (place / 'notes.json').write_text(json.dumps(notes, indent=2))
    lines = ['', '## The pictures', '',
             'Taken by `tools/capture_platforms.py` on GitHub\'s own machines '
             '(`.github/workflows/platform-screenshots.yml`). Each window is saved from '
             'the window itself, so it is what the game drew; the system\'s title bar is '
             'not the game\'s, and is in the picture of the whole screen where the system '
             'allows one to be taken.', '']
    for name, title in KEPT:
        lines += [f'### {title}', '', '| ' + ' | '.join(label for label, _ in labels) + ' |',
                  '|' + '---|' * len(labels),
                  '| ' + ' | '.join(
                      (f'![{title} on {label}]({label}/{name}.png)'
                       if (target / label / f'{name}.png').exists() else 'not taken')
                      for label, _ in labels) + ' |', '']
    screens = [label for label, _ in labels if (target / label / 'screen.png').exists()]
    if screens:
        lines += ['### The whole screen, with the system\'s own window frames', '']
        for label in screens:
            lines += [f'**{label}**', '', f'![The whole screen on {label}]({label}/screen.png)', '']
    names = ('tank', 'brain_tool', 'statistics', 'decorations')
    lines += ['## Where the game puts its windows', '',
              'Opened by the game itself and left where it put them: left, top, width, height '
              'on the screen. The picture of the whole screen for each system is further down.',
              '', '| System | ' + ' | '.join(name.replace('_', ' ').capitalize() for name in names)
              + ' |', '|---|' + '---|' * len(names)]
    for label, notes in labels:
        placed = notes.get('layout') or {}
        lines.append(f'| {label} | ' + ' | '.join(
            ', '.join(str(v) for v in placed[name]) if name in placed else 'not shown'
            for name in names) + ' |')
    lines += ['', 'The aquarium opens at the top left and stays above the other windows for '
              'its first five seconds: '
              + '; '.join(f"{label}: on top after 2 s {notes.get('tank_on_top_after_2s')}, "
                          f"after 9 s {notes.get('tank_on_top_after_9s')}"
                          for label, notes in labels) + '.']
    lines += ['', 'A Wayland compositor decides where a window goes and does not tell the '
              'program, so there the game can ask for a size but not a place, and reports '
              '0, 0 for all of them.', '',
              '## How big the squid is', '',
              '| System | Screen laid out for | Tank window | Squid | Share of the window\'s '
              'width | Tank scale |', '|---|---|---|---|---|---|']
    for label, notes in labels:
        scale = notes.get('scale') or {}
        style = notes['style']
        screen = 'x'.join(str(v) for v in (style.get('screen_assumed') or style['screen']))
        lines.append(f"| {label} | {screen} | "
                     f"{'x'.join(str(v) for v in scale.get('tank_window', ['?']))} | "
                     f"{'x'.join(str(v) for v in scale.get('squid', ['?']))} | "
                     f"{100 * scale.get('squid_share_of_width', 0):.1f}% | "
                     f"{scale.get('tank_scale', '?')} |")
    lines += ['', 'On the screen the game was designed for (2880x1920) the squid is 253 pixels '
              'wide in a 1344-pixel window: 18.8%. It takes the same share on every screen.', '',
              '## Which font draws what', '',
              '| System | A brain emoji in Fio UI text | On the Brain Designer button | '
              'The reset arrow |', '|---|---|---|---|']
    for label, notes in labels:
        fonts = notes.get('fonts') or {}
        ui = fonts.get('Fio UI', {})
        line = fonts.get('Dosidicus Line Emoji', {})
        lines.append(f"| {label} | {', '.join(ui.get('brain_drawn_by', ['?']))} | "
                     f"{', '.join(line.get('brain_drawn_by', ['?']))} | "
                     f"{', '.join(ui.get('arrow_drawn_by', ['?']))} |")
    lines += ['', '## Each machine', '']
    for label, notes in labels:
        lines.append(f"- **{label}**: {notes['system']}, Python {notes['python']}, "
                     f"Qt {notes['qt']}, real screen "
                     f"{'x'.join(str(v) for v in notes['style']['screen'])}"
                     + (f"; could not: {'; '.join(notes['problems'])}" if notes['problems'] else ''))
    with open(report, 'a') as handle:
        handle.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--label', default=sys.platform)
    parser.add_argument('--brain-size', default='',
                        help='WIDTHxHEIGHT: open the Brain Tool at this size instead of its '
                             'own (which a small screen cuts down)')
    parser.add_argument('--compare', type=Path, nargs='+')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--publish', type=Path, nargs='+',
                        help='TARGET then the captured folders')
    args = parser.parse_args()
    if args.publish:
        sys.exit(publish(args.publish[1:], args.publish[0]))
    if args.compare:
        sys.exit(compare(args.compare, args.report))
    if not args.output:
        parser.error('an output folder is needed')
    size = tuple(int(v) for v in args.brain_size.lower().split('x')) if args.brain_size else None
    sys.exit(capture(args.output, args.label, size))
