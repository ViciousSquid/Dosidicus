#!/usr/bin/env python3
"""Two Android devices in one visit: the real app, linked locally, for a gallery.

Each "device" is the Android app itself - its Kivy UI (dosidicus_mobile.ui)
and engine - in its own process and virtual display, phone-sized. Google
Nearby needs real radios, so a loopback socket stands in for it: the same
events in the same order (peer found, connection initiated, accepted on both
sides, connected, bytes), behind the same NearbyManager calls. Everything
above the transport is the app as shipped. The script presses the buttons a
player would: Host on one phone, Find and Connect on the other.

  Pip (hosts)   <-- loopback "Nearby" -->   Nova (visits)

Nudges, recorded in nudges.json: Nova kept playful and unafraid so it stays
and goes at Pip; Pip's aggression raised so the two scuffle.

Run: python tools/capture_android.py OUTPUT_DIR      (needs Xvfb and Kivy)
"""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('pip', 'nova')
NAMES = {'pip': 'Pip', 'nova': 'Nova'}
PORT = 47331
TIMEOUT = 150.0


class LoopbackNearby:
    """NearbyManager's interface over a local socket: one host, one finder."""

    ENDPOINT = 'loopback-1'

    def __init__(self, port):
        self.handlers = {}
        self.port = port
        self.sock = None
        self.peer_name = ''
        self.accepted = self.peer_accepted = self.connected = False
        self._lock = threading.Lock()

    # -- the events, delivered on the Kivy thread as Nearby's are -----------
    def _emit(self, event, *args):
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self._deliver(event, *args), 0)

    def _deliver(self, event, *args):
        callback = self.handlers.get(event)
        if callback:
            callback(*args)

    def _line(self, text):
        with self._lock:
            if self.sock is not None:
                self.sock.sendall((text + '\n').encode())

    def _read(self):
        buffer = b''
        while self.sock is not None:
            try:
                chunk = self.sock.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b'\n' in buffer:
                raw, buffer = buffer.split(b'\n', 1)
                self._on_line(raw.decode())
        if self.connected:
            self._emit('disconnected', self.ENDPOINT)

    def _on_line(self, line):
        kind, _, rest = line.partition(' ')
        if kind == 'NAME':                    # finder learns who is hosting
            self.peer_name = rest
            self._emit('peer_found', self.ENDPOINT, rest)
        elif kind == 'REQUEST':               # host: a finder asks to connect
            self.peer_name = rest
            self._line('INIT ' + self.my_name)
            self._emit('connection_initiated', self.ENDPOINT, rest, '4721')
        elif kind == 'INIT':                  # finder: the host answered
            self._emit('connection_initiated', self.ENDPOINT, rest, '4721')
        elif kind == 'ACCEPT':
            self.peer_accepted = True
            self._maybe_connected()
        elif kind == 'BYTES':
            self._emit('bytes', self.ENDPOINT, rest)

    def _maybe_connected(self):
        if self.accepted and self.peer_accepted and not self.connected:
            self.connected = True
            self._emit('connected', self.ENDPOINT)

    # -- NearbyManager's calls -----------------------------------------------
    def start(self):
        return True

    def host(self, name):
        self.my_name = name
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', self.port))
        server.listen(1)
        self._emit('status', 'Advertising')

        def serve():
            self.sock, _ = server.accept()
            server.close()
            self._line('NAME ' + name)
            self._read()
        threading.Thread(target=serve, daemon=True).start()

    def find(self):
        self.my_name = getattr(self, 'my_name', 'Squid')
        self._emit('status', 'Discovering')

        def connect():
            for _ in range(200):
                try:
                    self.sock = socket.create_connection(('127.0.0.1', self.port))
                    break
                except OSError:
                    time.sleep(.1)
            self._read()
        threading.Thread(target=connect, daemon=True).start()

    def request(self, name, endpoint_id):
        self.my_name = name
        self._line('REQUEST ' + name)

    def accept(self, endpoint_id):
        self.accepted = True
        self._line('ACCEPT')
        self._maybe_connected()

    def reject(self, endpoint_id):
        self.stop()

    def send(self, endpoint_id, data: bytes):
        self._line('BYTES ' + base64.b64encode(data).decode('ascii'))

    def disconnect(self, endpoint_id):
        self.stop()

    def stop(self):
        sock, self.sock = self.sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    @staticmethod
    def decode(base64_data):
        return base64.b64decode(base64_data)


def device(role, output):
    folder = output / role
    shots = output / 'shots'
    shots.mkdir(parents=True, exist_ok=True)
    folder.mkdir(parents=True, exist_ok=True)
    os.environ['KIVY_HOME'] = str(folder / 'kivy')
    os.environ.setdefault('KIVY_NO_ARGS', '1')
    sys.path.insert(0, str(ROOT / 'android'))
    from kivy.config import Config
    Config.set('graphics', 'width', '440')    # rows a multiple of 4 bytes, for screenshots
    Config.set('graphics', 'height', '900')
    Config.set('input', 'mouse', 'mouse,disable_multitouch')
    from kivy.clock import Clock
    from kivy.core.window import Window
    from dosidicus_mobile.ui import nearby
    nearby.is_available = lambda: True
    nearby.request_permissions = lambda: None
    class Manager(LoopbackNearby):             # what NearbyView constructs, and decodes with
        def __init__(self):
            super().__init__(PORT)
    nearby.NearbyManager = Manager
    from dosidicus_mobile.ui.app import DosidicusApp, TANK_SIZE
    from dosidicus_mobile.ui.nearby_screen import NOTICE_FLAG, NearbyView
    from dosidicus_mobile.engine import Simulation, Squid
    from src.brain_constants import ACTION_NEURONS

    data_dir = folder / 'data'
    data_dir.mkdir(exist_ok=True)
    (data_dir / NOTICE_FLAG).write_text('1')      # this player has said yes
    first = Simulation(tank_size=TANK_SIZE, squid=Squid(tank_size=TANK_SIZE))
    first.squid.name = NAMES[role]
    first.save(str(data_dir / 'squid_save.zip'))

    state = {'role': role, 'stage': 'start', 'shots': {}, 'nudges': [], 'notes': {}}
    started = time.monotonic()

    class Device(DosidicusApp):
        @property
        def user_data_dir(self):
            return str(data_dir)

    app = Device()

    def elapsed():
        return time.monotonic() - started

    def write():
        (folder / 'status.json').write_text(json.dumps(state, indent=2, default=str))

    def nudge(text):
        if text not in state['nudges']:
            state['nudges'].append(text)

    def shot(name, caption=''):
        if name in state['shots']:
            return
        made = Window.screenshot(name=str(shots / f'android-{role}-{name}.png'))
        if made and Path(made).exists():
            Path(made).rename(shots / f'android-{role}-{name}.png')
        state['shots'][name] = {'at': round(elapsed(), 1), 'caption': caption}
        write()

    def later(name, delay):
        key = f'_wait_{name}'
        state.setdefault(key, elapsed())
        return elapsed() - state[key] >= delay

    def drive(dt):
        try:
            sim = app.sim
            view = state.get('view')
            if state['stage'] == 'start' and elapsed() > 3:
                shot('home', caption=f'{NAMES[role]} at home')
                view = state['view'] = NearbyView(app)
                view.open()
                state['stage'] = 'nearby'
            if state['stage'] == 'nearby' and later('nearby', 1.5):
                if role == 'pip':
                    view._host()
                else:
                    view._find()
                state['stage'] = 'waiting'
            if state['stage'] == 'waiting':
                if role == 'nova' and view.peer_buttons and later('found', 1.0):
                    shot('found', caption='Nova finds Pip nearby')
                    next(iter(view.peer_buttons.values())).dispatch('on_release')   # tap
                    state['stage'] = 'requested'
                if role == 'pip' and view.visits:
                    state['stage'] = 'linked'
            if state['stage'] == 'requested' and view.visits:
                state['stage'] = 'linked'
            if state['stage'] == 'linked' and later('linked', 1.5):
                shot('connected', caption='Connected: a neural visit link')
                view.dismiss()                 # the visit carries on with it closed
                state['stage'] = 'visit'
            if state['stage'] == 'visit':
                live = [v for v in sim.peer_visits if not v.closed]
                if role == 'nova':
                    # Kept playful and unafraid, so it stays and goes at Pip.
                    nudge('Nova kept playful and unafraid while visiting (act_play 85, '
                          'flee/rest 0, anxiety 25)')
                    for name in ACTION_NEURONS:
                        sim.squid.brain.state[name] = 0.
                    sim.squid.brain.state.update(act_play=85., anxiety=25.)
                    sim.squid.sleepiness, sim.squid.hunger = 10., 20.
                    if live and live[0].away and later('away', 3.0):
                        shot('away', caption="Nova's phone while Nova is visiting: its brain "
                                             "runs here, its body is in Pip's tank")
                else:
                    visitors = [v for v in sim.visitors if v.get('remote')]
                    if visitors and later('arrived', 4.0):
                        shot('visitor', caption="Pip's phone: Nova's body in Pip's tank")
                    if visitors and later('aggro', 10.0):
                        nudge("Pip's aggression raised to 85 so the two scuffle")
                        sim.squid.brain.state['aggression'] = 85.
                        if sim.fight and sim.fight.get('phase') == 'fighting' and later('fighting', .8):
                            shot('fight', caption='A scuffle on Android: one cloud over the pair')
                            state['notes']['fight'] = dict(sim.fight, why=sim.fight.get('why'))
                    if 'fight' in state['shots'] and sim.fight is None and later('after', 2.0):
                        app._toggle_view()
                        state['stage'] = 'brain'
            if state['stage'] == 'brain' and later('brain', 2.0):
                shot('brain', caption="Pip's brain on Android: its SOCIAL band, grown from the visit")
                state['notes']['social'] = sorted(
                    n for n in sim.squid.brain.neuron_positions
                    if n in ('can_see_squid', 'squid_nearby', 'aquarium_nearby', 'social_play',
                             'social_fight', 'social_flee', 'aggression', 'recognises_squid'))
                state['stage'] = 'done'
            if role == 'nova' and state['stage'] == 'visit':
                other = output / 'pip' / 'status.json'
                try:
                    if json.loads(other.read_text()).get('stage') == 'done':
                        state['stage'] = 'done'
                except (OSError, ValueError):
                    pass
            if int(elapsed()) != state.get('second'):
                state['second'] = int(elapsed())
                state['status_line'] = getattr(sim, 'last_status', '')
                write()
            if state['stage'] == 'done' or elapsed() > TIMEOUT:
                state['finished_at'] = round(elapsed(), 1)
                state.pop('view', None)
                write()
                app.stop()
        except Exception:
            import traceback
            (folder / 'error.txt').write_text(traceback.format_exc())
            state.pop('view', None)
            app.stop()

    Clock.schedule_interval(drive, .25)
    app.run()
    return 0 if state['stage'] == 'done' else 3


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    children = []
    for role in ROLES:
        log = open(output / (role + '.log'), 'w')
        command = ['xvfb-run', '-a', '-s', '-screen 0 600x1000x24',
                   sys.executable, __file__, str(output), '--role', role]
        children.append((role, subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT),
                         log))
        time.sleep(1.0)
    codes = {}
    for role, child, log in children:
        codes[role] = child.wait(timeout=TIMEOUT + 60)
        log.close()
    status = {}
    for role in ROLES:
        try:
            status[role] = json.loads((output / role / 'status.json').read_text())
        except (OSError, ValueError):
            status[role] = {}
    summary = {'exit_codes': codes,
               'stages': {r: status[r].get('stage') for r in ROLES},
               'shots': {f'android-{r}-{n}': i for r in ROLES
                         for n, i in status[r].get('shots', {}).items()},
               'notes': {r: status[r].get('notes', {}) for r in ROLES},
               'nudges': sum((status[r].get('nudges', []) for r in ROLES), [])}
    (output / 'android.json').write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: summary[k] for k in ('exit_codes', 'stages')}, indent=2))
    print('shots:', ', '.join(summary['shots']))
    return 0 if all(c == 0 for c in codes.values()) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--role', choices=ROLES)
    args = parser.parse_args()
    if args.role:
        sys.exit(device(args.role, args.output))
    sys.exit(run(args.output))
