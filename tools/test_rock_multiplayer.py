#!/usr/bin/env python3
"""Exercise rock impacts over the real LAN protocol in two desktop processes.

Uses temporary saves and controlled neural activations to reproducibly exercise
both throw directions. No user's squid or production decision rules are changed.
Run: QT_QPA_PLATFORM=offscreen python tools/test_rock_multiplayer.py /tmp/rock-pair
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
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def worker(role, output):
    sys.path.insert(0, str(ROOT))
    folder = output / role
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'plugins'):
        (folder / name).symlink_to(ROOT / name, target_is_directory=True)
    shutil.copyfile(ROOT / 'config.ini', folder / 'config.ini')
    os.chdir(folder)
    from PyQt5 import QtCore, QtGui, QtWidgets
    from src.brain_constants import ACTION_NEURONS
    from src.config_manager import ConfigManager
    from plugins.multiplayer.identity import SquidIdentity
    # ConfigManager resolves its default beside src, irrespective of cwd.
    # Exercise its supported absolute filename override for every default
    # construction in these disposable processes, preserving tracked config.
    config_init = ConfigManager.__init__
    def isolated_config(self, config_filename='config.ini'):
        config_init(self, str(folder / 'config.ini') if config_filename == 'config.ini'
                    else config_filename)
    ConfigManager.__init__ = isolated_config
    app = QtWidgets.QApplication([])
    for method in ('question', 'information', 'warning', 'critical'):
        setattr(QtWidgets.QMessageBox, method, staticmethod(lambda *a, **k: 0))
    # These disposable test squids explicitly consent to irreversible visits.
    QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes)
    QtWidgets.QDialog.exec_ = lambda self: 0
    spec = importlib.util.spec_from_file_location('rock_test_main', ROOT / 'main.py')
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    class NoTutorial:
        def __init__(self, *a, **k): pass
        def exec_(self): return 0
        def get_result(self): return QtWidgets.QMessageBox.No
    main.TimedMessageBox = NoTutorial
    from src.personality import Personality
    window = main.MainWindow(specified_personality=Personality.ADVENTUROUS)
    window.show()
    window.resize(1100, 800)
    started = time.monotonic()
    state = {'role': role, 'plugin': None, 'reports': []}

    def quiet(play=0., rest=100.):
        brain = window.brain_window.brain_widget
        for name in ACTION_NEURONS:
            brain.state[name] = 0.
        brain.state['act_play'], brain.state['act_rest'] = play, rest

    def add_rock(x, y):
        pix = QtGui.QPixmap(16, 16); pix.fill(QtGui.QColor('gray'))
        rock = window.user_interface.scene.addPixmap(pix)
        rock.category, rock.filename = 'rock', 'rock01.png'
        rock.setPos(x-8, y-8)
        state.setdefault('rocks', []).append(rock)  # keep Python metadata
        return rock

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

    def tick():
        elapsed = time.monotonic() - started
        try:
            if elapsed > 9 and window.splash._ended and state['plugin'] is None:
                logic = window.tamagotchi_logic
                logic.stop(); window.brain_window.hebbian_timer.stop()
                window.squid.name = role
                window.squid.can_move = False
                window.squid.squid_x, window.squid.squid_y = 400., 300.
                window.squid.squid_item.setPos(400., 300.)
                window.squid.is_sleeping = False
                window.squid.health = 100.
                assert window.plugin_manager.enable_plugin('multiplayer')
                plugin = window.plugin_manager.plugins['multiplayer']['instance']
                state['plugin'] = plugin
                plugin.host_body.mating_chance = 0.
                window.brain_window.brain_widget.stop_worker()
                quiet()
                report = plugin.host_body._report
                def record(actor, kind, detail=None):
                    consequence = report(actor, kind, detail)
                    if kind == 'hit':
                        state['reports'].append(consequence.to_payload())
                    return consequence
                plugin.host_body._report = record
            plugin = state['plugin']
            if not plugin:
                return
            logic = window.tamagotchi_logic
            if int(elapsed) != state.get('heartbeat_at'):
                plugin.network_node.send_message('heartbeat', {'status': 'active'})
                state['heartbeat_at'] = int(elapsed)
            if (role == 'guest' and elapsed > 12 and not state.get('joined')
                    and plugin.network_node.known_nodes):
                payload = dict(node_id=plugin.network_node.node_id,
                    identity=SquidIdentity.from_squid(window.squid).to_payload(),
                    direction='right', image_direction_key='left', current_animation_frame=0)
                plugin.network_node.send_message('squid_exit', {'payload': payload})
                window.squid.squid_item.hide()
                state['joined'] = True
            actors = list(plugin.host_body.visitors.values())
            if role == 'host' and actors:
                actor = actors[0]
                node = plugin.visit_node_ids[actor.uuid]
                visual = plugin.entity_manager.remote_squids[node]['visual']
                if elapsed > 15 and not state.get('threw'):
                    actor.x, actor.y, actor.facing = 600., 300., 'left'
                    visual.setPos(actor.x, actor.y)
                    window.squid.current_view_angle = 0.
                    quiet(play=100., rest=0.)
                    centre = window.squid.squid_item.sceneBoundingRect().center()
                    rock = add_rock(centre.x(), centre.y())
                    assert logic.rock_interaction.attach_rock_to_squid(rock)
                    assert window.squid.throw_rock()
                    state['plan'] = dict(logic.rock_interaction.current_throw)
                    state['scene'] = [window.user_interface.scene.sceneRect().width(),
                                      window.user_interface.scene.sceneRect().height()]
                    state['target_rect'] = [visual.sceneBoundingRect().x(), visual.sceneBoundingRect().y(),
                                            visual.sceneBoundingRect().width(), visual.sceneBoundingRect().height()]
                    state['threw'] = True
                if elapsed > 18 and not state.get('replayed') and state['reports']:
                    # Re-envelope the same physical consequence twice over UDP.
                    plugin._send('consequence', state['reports'][0])
                    plugin._send('consequence', state['reports'][0])
                    state['replayed'] = True
                if elapsed > 20 and not state.get('visitor_rock'):
                    # Put a nearer rock in reach; the visitor's next play
                    # intent picks it up, and its following intent throws it.
                    actor.facing = 'left'
                    rock = add_rock(actor.x-15, actor.y+30)
                    state['visitor_rock'] = True
                if window.squid.health == 98.:
                    state['hit_at_home'] = True
            if role == 'guest' and plugin.visitor_mind.perception.away:
                mind = plugin.visitor_mind
                if window.squid.health == 98. and not state.get('felt'):
                    assert mind.session.hits_taken == 1
                    assert window.squid.mental_state_manager.is_state_active('startled')
                    logic.apply_input_neurons_to_brain()
                    brain = window.brain_window.brain_widget
                    assert brain.state['is_startled'] == 100.
                    brain.propagate_activations()
                    state['felt'] = True
                    state['neural_startle'] = brain.state['is_startled']
                if elapsed > 21:
                    quiet(play=100., rest=0.)
                if elapsed > 27 and state.get('felt'):
                    assert window.squid.health == 98., 'duplicate damage or self hit'
                    assert mind.session.hits_taken == 1 and mind.session.hits_given == 1
                    mind.end_visit()
                    assert logic.save_game()
                    saved = logic.save_manager.get_latest_save()
                    with zipfile.ZipFile(saved) as archive:
                        assert json.loads(archive.read('game_state.json'))['squid']['health'] == 98.
                        permanent = json.loads(archive.read('LongTerm.json'))
                        assert any(m.get('category') == 'social' and isinstance(m.get('value'), dict)
                            and m['value'].get('detail', {}).get('hits_taken') == 1 for m in permanent)
                    state['save_verified'] = True
                    state['memory_hits'] = [m['value']['detail'] for m in
                        window.squid.memory_manager.short_term_memory + window.squid.memory_manager.long_term_memory
                        if m.get('category') == 'social' and isinstance(m.get('value'), dict)
                        and m['value'].get('detail', {}).get('hits_taken')]
                    assert len(state['memory_hits']) == 1
                    state['complete'] = True
            if elapsed > 30:
                assert state.get('felt') if role == 'guest' else state.get('hit_at_home')
                result = {k: v for k, v in state.items() if k not in ('plugin', 'rocks')}
                result['health'] = window.squid.health
                (folder / 'result.json').write_text(json.dumps(result, indent=2))
                finish()
            status = {k: v for k, v in state.items() if k not in ('plugin', 'rocks')}
            status.update(health=window.squid.health, elapsed=elapsed,
                          actors=[dict(x=a.x, y=a.y, action=a.action) for a in actors],
                          away=plugin.visitor_mind.perception.away,
                          flight=logic.rock_interaction.flying_rock is not None)
            (folder / 'status.json').write_text(json.dumps(status, indent=2))
            if elapsed > 45:
                raise RuntimeError('startup timed out')
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
            code = child.wait(timeout=60)
            log.close()
            if code:
                raise RuntimeError(f'{role} exited {code}; see {output / role / "error.txt"}')
        results = {role: json.loads((output / role / 'result.json').read_text())
                   for role in ('host', 'guest')}
        assert results['host']['health'] == results['guest']['health'] == 98.
        assert results['guest']['complete']
        print(json.dumps(results, indent=2))
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
