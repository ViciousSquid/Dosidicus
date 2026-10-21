#!/usr/bin/env python3
"""Two desktop processes on the real LAN protocol: a squid ventures out by itself.

Nothing here tells the guest to leave. Both games run as they do for a player,
with multiplayer enabled: the guest (adventurous) hears the host's aquarium,
grows its aquarium_nearby sense, and leaves when its own network is driving it
out (src/venturing.py); the host (timid, so it stays home) admits it. The
harness only starts both squid awake, with temporary saves and config.

Run: QT_QPA_PLATFORM=offscreen python tools/test_venture_multiplayer.py /tmp/venture-pair
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 180.0


def worker(role, output):
    sys.path.insert(0, str(ROOT))
    folder = output / role
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'plugins'):
        (folder / name).symlink_to(ROOT / name, target_is_directory=True)
    shutil.copyfile(ROOT / 'config.ini', folder / 'config.ini')
    os.chdir(folder)
    from PyQt5 import QtCore, QtWidgets
    from src.brain_constants import AQUARIUM_SENSE
    from src.config_manager import ConfigManager
    config_init = ConfigManager.__init__

    def isolated_config(self, config_filename='config.ini'):
        config_init(self, str(folder / 'config.ini') if config_filename == 'config.ini'
                    else config_filename)
    ConfigManager.__init__ = isolated_config
    app = QtWidgets.QApplication([])
    for method in ('information', 'warning', 'critical'):
        setattr(QtWidgets.QMessageBox, method, staticmethod(lambda *a, **k: 0))
    # These disposable test squids consent to irreversible visits.
    QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes)
    QtWidgets.QDialog.exec_ = lambda self: 0
    spec = importlib.util.spec_from_file_location('venture_test_main', ROOT / 'main.py')
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

    class NoTutorial:
        def __init__(self, *a, **k): pass
        def exec_(self): return 0
        def get_result(self): return QtWidgets.QMessageBox.No
    main.TimedMessageBox = NoTutorial
    from src.personality import Personality
    window = main.MainWindow(specified_personality=(Personality.ADVENTUROUS if role == 'guest'
                                                    else Personality.TIMID))
    window.show()
    window.resize(1100, 800)
    started = time.monotonic()
    state = {'role': role, 'plugin': None, 'trace': []}

    def finish(code=0):
        timer.stop()
        if state['plugin']:
            window.plugin_manager.unload_all_plugins()
        window.tamagotchi_logic.stop()
        window.squid.retire()
        window.brain_window.brain_widget.stop_worker()
        window.brain_window.brain_widget._cleanup_render_worker()
        window._cancel_game_callbacks()
        window.splash.timer.stop()
        window.brain_window.deleteLater(); window.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.exit(code)

    def write(name):
        result = {k: v for k, v in state.items() if k != 'plugin'}
        (folder / name).write_text(json.dumps(result, indent=2, default=str))

    def tick():
        elapsed = time.monotonic() - started
        try:
            squid = window.squid
            brain = window.brain_window.brain_widget
            if elapsed > 9 and window.splash._ended and state['plugin'] is None:
                window.squid.name = role
                squid.is_sleeping = False
                squid.health = 100.
                for drive, value in (('hunger', 15.), ('sleepiness', 5.), ('anxiety', 15.),
                                     ('happiness', 70.), ('curiosity', 70.)):
                    setattr(squid, drive, value)
                if role == 'host':
                    squid.can_move = False
                assert window.plugin_manager.enable_plugin('multiplayer')
                state['plugin'] = window.plugin_manager.plugins['multiplayer']['instance']
                state['plugin'].host_body.mating_chance = 0.
            plugin = state['plugin']
            if not plugin:
                return
            if int(elapsed) != state.get('heartbeat_at'):
                state['heartbeat_at'] = int(elapsed)
                plugin.network_node.send_message('heartbeat', {'status': 'active'})
                if role == 'guest':
                    state['trace'].append({
                        't': round(elapsed, 1),
                        'sense': AQUARIUM_SENSE in brain.neuron_positions,
                        'heard': brain.state.get(AQUARIUM_SENSE),
                        'act_move': round(float(brain.state.get('act_move', 0) or 0), 1),
                        'draw': brain.weights.get((AQUARIUM_SENSE, 'act_move')),
                        'why_not': squid.why_not_venturing(),
                        'x': round(squid.squid_x), 'status': squid.status})
                    write('status.json')
            if role == 'guest' and plugin.visitor_mind.perception.away and not state.get('complete'):
                state['away_after'] = round(elapsed, 1)
                thoughts = [text for _, text in getattr(brain, 'social_thoughts', [])]
                state['thoughts'] = thoughts[-6:]
                state['complete'] = True
            if role == 'host' and plugin.host_body.visitors and not state.get('complete'):
                state['admitted_after'] = round(elapsed, 1)
                state['complete'] = True
            if state.get('complete') and elapsed > state.get('away_after',
                                                             state.get('admitted_after', 0)) + 3:
                write('result.json')
                finish()
            if elapsed > TIMEOUT:
                write('result.json')
                raise RuntimeError(f'{role}: no visit after {TIMEOUT:.0f}s')
        except Exception:
            import traceback
            (folder / 'error.txt').write_text(traceback.format_exc())
            finish(1)
    timer = QtCore.QTimer(); timer.timeout.connect(tick); timer.start(100)
    return app.exec_()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    children = []
    try:
        for role in ('host', 'guest'):
            log = open(output / (role + '.log'), 'w')
            child = subprocess.Popen([sys.executable, __file__, str(output), '--role', role],
                                     stdout=log, stderr=subprocess.STDOUT)
            children.append((role, child, log))
        for role, child, log in children:
            code = child.wait(timeout=TIMEOUT + 60)
            log.close()
            if code:
                raise RuntimeError(f'{role} exited {code}; see {output / role / "error.txt"}')
        results = {role: json.loads((output / role / 'result.json').read_text())
                   for role in ('host', 'guest')}
        assert results['guest']['complete'] and results['host']['complete']
        print(json.dumps({role: {k: v for k, v in r.items() if k != 'trace'}
                          for role, r in results.items()}, indent=2))
    finally:
        for _, child, log in children:
            if child.poll() is None:
                child.terminate(); child.wait(timeout=10)
            log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--role', choices=('host', 'guest'))
    args = parser.parse_args()
    target = args.output.resolve()
    if args.role:
        sys.exit(worker(args.role, target))
    run(target)
