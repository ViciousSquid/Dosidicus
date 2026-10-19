#!/usr/bin/env python3
"""Record two real desktop processes communicating over the LAN protocol.

Uses isolated saves and deterministic scene setup: the contest is triggered,
the rare mating roll is made certain in the demo host only, and starvation's
last tick is accelerated. Production chances and timings are unchanged.
Requires PyQt5, NumPy and ffmpeg. On a server use QT_QPA_PLATFORM=offscreen.
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


def worker(role, output):
    sys.path.insert(0, str(ROOT))
    folder = output / role
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'plugins'):
        if not (folder / name).exists():
            (folder / name).symlink_to(ROOT / name, target_is_directory=True)
    shutil.copyfile(ROOT / 'config.ini', folder / 'config.ini')
    frames = folder / 'frames'
    frames.mkdir(exist_ok=True)
    os.chdir(folder)
    from PyQt5 import QtCore, QtGui, QtWidgets
    from src.brain_constants import ACTION_NEURONS
    from plugins.multiplayer.identity import SquidIdentity
    app = QtWidgets.QApplication([])
    for method in ('question', 'information', 'warning', 'critical'):
        setattr(QtWidgets.QMessageBox, method, staticmethod(lambda *a, **k: 0))
    QtWidgets.QDialog.exec_ = lambda self: 0
    spec = importlib.util.spec_from_file_location('desktop_demo_main', ROOT / 'main.py')
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

    class NoTutorial:
        def __init__(self, *a, **k): pass
        def exec_(self): return 0
        def get_result(self): return QtWidgets.QMessageBox.No
    main.TimedMessageBox = NoTutorial
    window = main.MainWindow()
    window.setWindowTitle('Dosidicus — ' + role.capitalize())
    window.show()
    window.resize(1100, 800)
    events = []
    initial_uuid = str(window.squid.uuid)
    started = time.monotonic()
    state = {'plugin': None, 'joined': False, 'fought': False, 'mating_setup': False,
             'died': False, 'frame': 0, 'snapshots': set()}
    report_message = window.user_interface.show_message

    def show_message(message, *a, **k):
        events.append(dict(at=round(time.monotonic()-started, 2), message=str(message)))
        return report_message(message, *a, **k)
    window.user_interface.show_message = show_message
    begin = window._begin_new_life
    def observe_handoff(*a, **k):
        cover = window._hatch_cover
        before = cover.grab().toImage()
        cover.grab().save(str(output / 'handoff-before.png'))
        begin(*a, **k)
        after = window.splash.grab().toImage()
        window.splash.grab().save(str(output / 'handoff-after.png'))
        state['handoff_identical'] = before == after
    window._begin_new_life = observe_handoff

    def snapshot(name):
        if name not in state['snapshots']:
            state['snapshots'].add(name)
            window.grab().save(str(output / f'{role}-{name}.png'))

    def tick():
        elapsed = time.monotonic() - started
        try:
            if elapsed > 9 and window.splash._ended and state['plugin'] is None:
                window.tamagotchi_logic.stop()
                window.brain_window.hebbian_timer.stop()
                window.squid.name = 'Coral' if role == 'host' else 'Indigo'
                window.squid.apply_tint(QtGui.QColor('#e9a479' if role == 'host' else '#8f9ee8'))
                window.squid.can_move = False
                window.squid.squid_x, window.squid.squid_y = 400, 350
                window.squid.squid_item.setPos(400, 350)
                assert window.plugin_manager.enable_plugin('multiplayer'), 'multiplayer did not enable'
                plugin = window.plugin_manager.plugins['multiplayer']['instance']
                state['plugin'] = plugin
                plugin.host_body.mating_chance = 0
                brain = window.brain_window.brain_widget
                brain.stop_worker()
                brain.weights.clear()
                for name in ACTION_NEURONS:
                    brain.state[name] = 0
                brain.state['act_play'] = 100
                window.squid.is_sleeping = False
            plugin = state['plugin']
            if plugin is not None:
                if role == 'guest' and elapsed > 12 and not state['joined']:
                    payload = dict(node_id=plugin.network_node.node_id,
                                   identity=SquidIdentity.from_squid(window.squid).to_payload(),
                                   direction='right', image_direction_key='left',
                                   current_animation_frame=1, name=window.squid.name)
                    plugin.network_node.send_message('squid_exit', {'payload': payload})
                    window.squid.squid_item.setVisible(False)
                    window.user_interface.show_message('Indigo is visiting Coral’s tank.')
                    state['joined'] = True
                visitors = list(plugin.host_body.visitors.values()) if plugin.host_body else []
                if role == 'host' and visitors:
                    actor = visitors[0]
                    if elapsed > 13 and not state['fought']:
                        window.squid.is_sleeping = False
                        actor.x, actor.y = 620, 350
                        plugin.host_body.publish_presence(actor)
                        plugin.conspecific_view.note_contest(actor.identity, squid=window.squid)
                        window.user_interface.show_message('Coral and Indigo are fighting!')
                        state['fought'] = True
                    if plugin.entity_manager._fight_clouds:
                        snapshot('fight')
                        state['max_clouds'] = max(state.get('max_clouds', 0), len(plugin.entity_manager._fight_clouds))
                    if elapsed > 17 and not state['mating_setup']:
                        window.squid.can_move = True
                        actor.mating_rolled = False
                        actor.contact_since = None
                        plugin.host_body.mating_chance = 1.0
                        state['mating_setup'] = True
                lifecycle = window.squid.lifecycle
                if role == 'host' and lifecycle.egg:
                    snapshot('egg')
                    if elapsed > 26 and not state['died']:
                        window.squid.is_sleeping = False
                        window.squid.hunger, window.squid.health = 100, .05
                        window.tamagotchi_logic.update_statistics()
                        state['died'] = True
                    if lifecycle.is_dead:
                        snapshot('parent-dead')
                if role == 'host' and str(window.squid.uuid) != initial_uuid:
                    if window.splash.isVisible():
                        if window.splash.frame_index >= 2:
                            snapshot('hatching')
                    else:
                        snapshot('newborn')
                if role == 'guest' and plugin.visitor_mind.perception.away:
                    snapshot('visiting')
                status = dict(role=role, elapsed=round(elapsed, 2), initial_uuid=initial_uuid,
                              uuid=str(window.squid.uuid), stage=window.squid.lifecycle.stage,
                              egg=window.squid.lifecycle.egg,
                              peers=len(getattr(plugin.network_node, 'known_nodes', {})),
                              visitors=len(visitors),
                              away=bool(plugin.visitor_mind and plugin.visitor_mind.perception.away),
                              max_clouds=state.get('max_clouds', 0),
                              handoff_identical=state.get('handoff_identical'), events=events)
                status['can_move'] = window.squid.can_move
                status['host_actors'] = [dict(x=a.x, y=a.y, seq=a.seq_seen, action=a.action,
                    contact=a.contact_since, rolled=a.mating_rolled, busy=a.body_busy_until,
                    distance=((a.x-window.squid.squid_x)**2+(a.y-window.squid.squid_y)**2)**.5)
                    for a in visitors]
                status['motors'] = {name: window.brain_window.brain_widget.state.get(name) for name in ACTION_NEURONS}
                (folder / 'status.json').write_text(json.dumps(status, indent=2))
            if elapsed > 10:
                window.grab().save(str(frames / f'{state["frame"]:05d}.png'))
                state['frame'] += 1
            if elapsed > 43:
                timer.stop()
                window.plugin_manager.unload_all_plugins()
                window.tamagotchi_logic.stop()
                window.squid.retire()
                window.brain_window.brain_widget.stop_worker()
                window.brain_window.brain_widget._cleanup_render_worker()
                window._cancel_game_callbacks()
                window.splash.timer.stop()
                window.brain_window.deleteLater()
                window.deleteLater()
                QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
                app.quit()
        except Exception:
            import traceback
            (folder / 'error.txt').write_text(traceback.format_exc())
            timer.stop()
            app.exit(1)
    timer = QtCore.QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec_()


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    processes = []
    for role in ('host', 'guest'):
        log = open(output / f'{role}.log', 'w')
        process = subprocess.Popen([sys.executable, __file__, str(output), '--role', role],
                                   stdout=log, stderr=subprocess.STDOUT)
        processes.append((role, process, log))
    for role, process, log in processes:
        code = process.wait(timeout=80)
        log.close()
        if code:
            raise RuntimeError(f'{role} exited {code}; inspect {output / role / "error.txt"} and {output / (role+".log")}')
    host = json.loads((output / 'host/status.json').read_text())
    guest = json.loads((output / 'guest/status.json').read_text())
    assert host['uuid'] != host['initial_uuid'], 'egg did not become a new game'
    assert host['handoff_identical'], 'handoff frames differ'
    assert host['max_clouds'] == 1, 'expected one shared fighting cloud'
    assert (output / 'host-egg.png').exists(), 'mating did not produce an egg'
    for role in ('host', 'guest'):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '10',
                        '-i', str(output / role / 'frames/%05d.png'), '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                        str(output / f'{role}.mp4')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(output/'host.mp4'),
                    '-i', str(output/'guest.mp4'), '-filter_complex', 'hstack=inputs=2',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    str(output/'two-instances.mp4')], check=True)
    print(json.dumps(dict(host=host, guest=guest), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--role', choices=('host', 'guest'))
    args = parser.parse_args()
    output = args.output.resolve()
    if args.role:
        sys.exit(worker(args.role, output))
    run(output)
