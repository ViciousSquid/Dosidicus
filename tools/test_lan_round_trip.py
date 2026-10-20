#!/usr/bin/env python3
"""A small LAN of squid, in real processes: discovery, a visit, a round trip.

Three desktop games on the real multicast protocol - an adventurous traveller
and two timid hosts - and nothing tells any squid what to do:

  1. DISCOVERY  every game hears the other two (heartbeats);
  2. VENTURING  the traveller grows its aquarium_nearby sense and leaves when
                its own network drives it out, addressing ONE host;
  3. VISIT      exactly that host admits it, and no other;
  4. SOCIAL     in the host tank the two squid see each other: each grows
                can_see_squid, and both open an encounter;
  5. HOME       the traveller comes home by its own rule (always home to
                sleep): the harness only compresses time, setting its
                sleepiness as if hours had passed once the encounter has run;
  6. CHANGED    its save holds the social structure it grew over there, with
                its provenance - and a FRESH process loading that save still
                has it.

The simulation runs at its own 1 FPS. Temporary folders, saves and config;
mating is switched off so the round trip stays a round trip.

Run: QT_QPA_PLATFORM=offscreen python tools/test_lan_round_trip.py /tmp/lan
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
ROLES = ('traveller', 'host_a', 'host_b')
TIMEOUT = 300.0
VISIT_BEFORE_BEDTIME = 20.0     # seconds of encounter before the night falls


def _setup(folder):
    """A disposable game folder: its own config and saves, shared assets."""
    sys.path.insert(0, str(ROOT))
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('images', 'plugins'):
        if not (folder / name).exists():
            (folder / name).symlink_to(ROOT / name, target_is_directory=True)
    if not (folder / 'config.ini').exists():
        shutil.copyfile(ROOT / 'config.ini', folder / 'config.ini')
    os.chdir(folder)
    from PyQt5 import QtWidgets
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
    spec = importlib.util.spec_from_file_location('lan_test_main', ROOT / 'main.py')
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

    class NoTutorial:
        def __init__(self, *a, **k): pass
        def exec_(self): return 0
        def get_result(self): return QtWidgets.QMessageBox.No
    main.TimedMessageBox = NoTutorial
    return app, main


def _social_structure(brain):
    from src.brain_constants import SOCIAL_NEURONS, SOCIAL_SENSORS
    return sorted(n for n in list(SOCIAL_SENSORS) + list(SOCIAL_NEURONS)
                  if n in brain.neuron_positions)


def _shutdown(app, window, timer, plugin, code=0):
    from PyQt5 import QtCore
    timer.stop()
    if plugin:
        window.plugin_manager.unload_all_plugins()
    window.tamagotchi_logic.stop()
    window.squid.retire()
    window.brain_window.brain_widget.stop_worker()
    window.brain_window.brain_widget._cleanup_render_worker()
    window._cancel_game_callbacks()
    splash = getattr(window, 'splash', None)       # a loaded game has none
    if splash is not None:
        splash.timer.stop()
    window.brain_window.deleteLater(); window.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.exit(code)


def worker(role, output):
    folder = output / role
    app, main = _setup(folder)
    from PyQt5 import QtCore
    from src.personality import Personality
    window = main.MainWindow(specified_personality=(Personality.ADVENTUROUS
                                                    if role == 'traveller'
                                                    else Personality.TIMID))
    window.show()
    window.resize(1100, 800)
    started = time.monotonic()
    state = {'role': role, 'plugin': None, 'trace': []}
    timer = QtCore.QTimer()

    def write(name):
        data = {k: v for k, v in state.items() if k != 'plugin'}
        (folder / name).write_text(json.dumps(data, indent=2, default=str))

    def tick():
        elapsed = time.monotonic() - started
        try:
            squid = window.squid
            brain = window.brain_window.brain_widget
            if elapsed > 9 and window.splash._ended and state['plugin'] is None:
                squid.name = role
                squid.is_sleeping = False
                squid.health = 100.
                for drive, value in (('hunger', 15.), ('sleepiness', 5.), ('anxiety', 15.),
                                     ('happiness', 70.), ('curiosity', 70.)):
                    setattr(squid, drive, value)
                state['uuid'] = str(squid.uuid)
                state['before'] = _social_structure(brain)
                assert window.plugin_manager.enable_plugin('multiplayer')
                state['plugin'] = window.plugin_manager.plugins['multiplayer']['instance']
                state['plugin'].host_body.mating_chance = 0.
                state['node_id'] = state['plugin'].network_node.node_id
            plugin = state['plugin']
            if not plugin:
                return
            if int(elapsed) != state.get('second'):
                state['second'] = int(elapsed)
                plugin.network_node.send_message('heartbeat', {'status': 'active'})
                state['heard'] = sorted(plugin._peers_last_heard)
                state['social'] = _social_structure(brain)
                row = {'t': round(elapsed), 'x': round(squid.squid_x),
                       'y': round(squid.squid_y), 'status': squid.status,
                       'social': state['social'],
                       'away': plugin.visitor_mind.perception.away,
                       'why_not': squid.why_not_venturing()}
                for actor in plugin.host_body.visitors.values():
                    row['visitor'] = {'x': round(actor.x), 'y': round(actor.y),
                                      'facing': actor.facing, 'action': actor.action,
                                      'sees': plugin.host_body.build_frame(actor).sensors}
                state['trace'].append(row)
                write('status.json')

            if role == 'traveller':
                travel(plugin, squid, brain, elapsed)
            else:
                host(plugin, squid, brain, elapsed)
            if elapsed > TIMEOUT:
                write('result.json')
                raise RuntimeError(f'{role}: timed out at {state.get("stage")}')
        except Exception:
            import traceback
            (folder / 'error.txt').write_text(traceback.format_exc())
            _shutdown(app, window, timer, state['plugin'], 1)

    def travel(plugin, squid, brain, elapsed):
        mind = plugin.visitor_mind
        if mind.perception.away and 'away_at' not in state:
            state.update(away_at=round(elapsed, 1), asked=plugin._asked_to_visit,
                         stage='visiting')
        if 'away_at' in state and 'home_at' not in state:
            if mind.session is not None:
                state['encounter_opened'] = True
            if 'can_see_squid' in brain.neuron_positions and 'saw_at' not in state:
                state['saw_at'] = round(elapsed, 1)
            visited = elapsed - state['away_at']
            if not state.get('night') and (('saw_at' in state and visited >= VISIT_BEFORE_BEDTIME)
                                           or visited >= 3 * VISIT_BEFORE_BEDTIME):
                squid.sleepiness = 100.0          # hours pass; what it does is its own
                state['night'] = round(elapsed, 1)
                state['stage'] = 'bedtime'
            if not mind.perception.away:
                state['home_at'] = round(elapsed, 1)
                state['slept_at_home'] = bool(squid.is_sleeping)
                state['stage'] = 'home'
                state['thoughts'] = [t for _, t in getattr(brain, 'social_thoughts', [])][-8:]
        if 'home_at' in state and squid.is_sleeping:
            state['slept_at_home'] = True       # sleep is quick: 28 sleepiness a second
        if 'home_at' in state and elapsed > state['home_at'] + 3 and not state.get('saved'):
            assert window.tamagotchi_logic.save_game()
            saved = window.tamagotchi_logic.save_manager.get_latest_save()
            with zipfile.ZipFile(saved) as archive:
                state['save'] = str(saved)
                state['save_mentions'] = {
                    name: [n for n in state['social'] if n in archive.read(name).decode('utf-8', 'replace')]
                    for name in archive.namelist() if name.endswith('.json')}
                permanent = json.loads(archive.read('LongTerm.json')) \
                    if 'LongTerm.json' in archive.namelist() else []
            state['long_term_social'] = [m.get('key') for m in permanent
                                         if m.get('category') == 'social']
            ledger = getattr(brain, 'ledger', None)
            state['provenance'] = {n: getattr(ledger.origins.get(n), 'deficit_summary', '')
                                   for n in state['social']} if ledger else {}
            state['encounter_synapses'] = {f'{s}->{d}': round(v, 3) for (s, d), v in
                                           brain.weights.items() if ledger and
                                           ledger.edge_totals((s, d)).get('encounter')}
            state['saved'] = True
            state['complete'] = True
            write('result.json')
            _shutdown(app, window, timer, plugin)

    def host(plugin, squid, brain, elapsed):
        if plugin.host_body.visitors and 'admitted_at' not in state:
            actor = next(iter(plugin.host_body.visitors.values()))
            state.update(admitted_at=round(elapsed, 1), visitor=actor.uuid)
        if state.get('visitor') and state['visitor'] in plugin.open_encounters:
            state['encounter_opened'] = True
        done = output / 'traveller' / 'result.json'
        if done.exists() and json.loads(done.read_text()).get('complete'):
            state['complete'] = True
            write('result.json')
            _shutdown(app, window, timer, plugin)

    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec_()


def reload(output):
    """A fresh process opens the traveller's save: is it still changed?"""
    folder = output / 'traveller'
    app, main = _setup(folder)
    from PyQt5 import QtCore
    window = main.MainWindow()                 # no personality: load the save
    window.show()
    started = time.monotonic()
    timer = QtCore.QTimer()

    def tick():
        try:
            if time.monotonic() - started < 8:
                return
            brain = window.brain_window.brain_widget
            ledger = getattr(brain, 'ledger', None)
            social = _social_structure(brain)
            memories = (window.squid.memory_manager.get_all_long_term_memories()
                        + window.squid.memory_manager.get_all_short_term_memories())
            result = {'uuid': str(window.squid.uuid), 'social': social,
                      'provenance': {n: getattr(ledger.origins.get(n), 'deficit_summary', '')
                                     for n in social} if ledger else {},
                      'social_memories': [m.get('key') for m in memories
                                          if m.get('category') == 'social']}
            (folder / 'reload.json').write_text(json.dumps(result, indent=2))
            _shutdown(app, window, timer, None)
        except Exception:
            import traceback
            (folder / 'reload_error.txt').write_text(traceback.format_exc())
            _shutdown(app, window, timer, None, 1)
    timer.timeout.connect(tick)
    timer.start(500)
    return app.exec_()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    children = []
    try:
        for role in ROLES:
            log = open(output / (role + '.log'), 'w')
            child = subprocess.Popen([sys.executable, __file__, str(output), '--role', role],
                                     stdout=log, stderr=subprocess.STDOUT)
            children.append((role, child, log))
        for role, child, log in children:
            code = child.wait(timeout=TIMEOUT + 90)
            log.close()
            if code:
                raise RuntimeError(f'{role} exited {code}; see {output / role / "error.txt"}')
        r = {role: json.loads((output / role / 'result.json').read_text()) for role in ROLES}
        traveller, hosts = r['traveller'], [r['host_a'], r['host_b']]

        # 1. Discovery: everybody heard everybody.
        nodes = {role: r[role]['node_id'] for role in ROLES}
        for role in ROLES:
            assert set(r[role]['heard']) >= set(nodes.values()) - {nodes[role]}, (role, r[role]['heard'])
        # 2-3. It left by itself, asked one host, and only that host took it in.
        assert traveller['before'] == [] and 'away_at' in traveller
        admitted = [h for h in hosts if 'admitted_at' in h]
        assert len(admitted) == 1, 'admitted by more than one host'
        assert admitted[0]['node_id'] == traveller['asked']
        assert admitted[0]['visitor'] == traveller['uuid']
        # 4. Social behaviour: each saw the other, both had an encounter.
        assert 'can_see_squid' in traveller['social'] and traveller.get('encounter_opened')
        assert 'can_see_squid' in admitted[0]['social'] and admitted[0].get('encounter_opened')
        # 5. Home by its own rule.
        assert 'home_at' in traveller and traveller.get('slept_at_home')
        assert any('went home to sleep' in t for t in traveller['thoughts']), traveller['thoughts']
        # 6. Changed, for good: in the save, and in a fresh process.
        assert set(traveller['social']) >= {'aquarium_nearby', 'can_see_squid'}
        assert any('can_see_squid' in found for found in traveller['save_mentions'].values())
        reloader = subprocess.run([sys.executable, __file__, str(output), '--role', 'reload'],
                                  stdout=open(output / 'reload.log', 'w'),
                                  stderr=subprocess.STDOUT, timeout=180)
        assert reloader.returncode == 0, 'reload failed; see traveller/reload_error.txt'
        again = json.loads((output / 'traveller' / 'reload.json').read_text())
        assert again['uuid'] == traveller['uuid']
        assert set(again['social']) >= set(traveller['social']), (again, traveller['social'])
        assert again['provenance'].get('can_see_squid')
        summary = {
            'nodes': nodes,
            'heard': {role: r[role]['heard'] for role in ROLES},
            'asked': traveller['asked'], 'admitted_by': admitted[0]['role'],
            'left_home_at': traveller['away_at'], 'saw_resident_at': traveller.get('saw_at'),
            'home_at': traveller['home_at'],
            'traveller_grew': traveller['social'], 'host_grew': admitted[0]['social'],
            'thoughts': traveller['thoughts'],
            'provenance': traveller['provenance'],
            'encounter_synapses': traveller['encounter_synapses'],
            'long_term_social': traveller['long_term_social'],
            'after_reload': again,
        }
        (output / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
    finally:
        for _, child, log in children:
            if child.poll() is None:
                child.terminate(); child.wait(timeout=10)
            log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--role', choices=ROLES + ('reload',))
    args = parser.parse_args()
    target = args.output.resolve()
    if args.role == 'reload':
        sys.exit(reload(target))
    if args.role:
        sys.exit(worker(args.role, target))
    run(target)
