#!/usr/bin/env python3
"""The headless trainer, watched and steered from a web page.

    python headless/headless_trainer.py --serve            # then open the address it prints
    python headless/headless_trainer.py --serve 8765 --brain my.json --seed 3

There is one trainer: HeadlessSimulation, which runs the same brain modules
the game does. This puts a page in front of it. The page shows the brain it
is training as it trains - every neuron's value, every synapse, each neuron
it grows and why - and can pause it, step it tick by tick, change its speed,
intervene from outside (feed, startle, clean - recorded as interventions,
never as something the squid earned), start again from a seed, load a brain
and take the trained brain away.

It listens on this computer only (127.0.0.1) and uses nothing outside the
Python standard library.
"""
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).resolve().parent / 'trainer.html'
SPEEDS = (1, 10, 100, 1000, 0)          # ticks a second; 0 is as fast as it will go
INTERVENTIONS = ('feed', 'startle', 'clean')
DRIVES = ('hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity')


class LiveTrainer:
    """One HeadlessSimulation, stepped by a thread, read and steered safely."""

    def __init__(self, config=None, brain=None, scenario=None):
        self._lock = threading.RLock()
        self._closed = False
        self.running = False
        self.speed = 10
        self.ticks_per_second = 0.0
        self.log = deque(maxlen=200)
        self._brain_path = brain
        self._scenario = scenario
        self._build(config)
        self._thread = threading.Thread(target=self._loop, name='live-trainer', daemon=True)
        self._thread.start()

    # ------------------------------------------------------------ building
    def _build(self, config):
        from headless.headless_trainer import HeadlessSimulation, TRAINING_SCENARIOS
        from src.portable_brain import TrainingConfig
        self.config = config or TrainingConfig()
        self.sim = HeadlessSimulation(self.config)
        self.sim.tick = 0
        self.log.clear()
        if self._brain_path:
            if not self.sim.load_brain(self._brain_path):
                raise ValueError(f'could not load the brain in {self._brain_path}')
            self._say(f'Loaded the brain in {Path(self._brain_path).name}')
        if self._scenario:
            if self._scenario not in TRAINING_SCENARIOS or not self.sim.load_scenario(self._scenario):
                raise ValueError(f'unknown scenario: {self._scenario}')
            self._say(f'Scenario: {TRAINING_SCENARIOS[self._scenario].name}')
        self._known = set(self.sim.brain.positions)

    def _say(self, text, kind='note'):
        self.log.append({'tick': int(getattr(self.sim, 'tick', 0)), 'kind': kind, 'text': str(text)})

    # ------------------------------------------------------------ stepping
    def _one_tick(self):
        sim = self.sim
        sim._process_events()
        sim._simulation_step()
        sim.tick += 1
        sim.stats['ticks_completed'] = sim.tick
        positions = sim.brain.positions
        if len(positions) != len(self._known):
            for name in set(positions) - self._known:
                self._say(self._why(name), kind='neuron')
            for name in self._known - set(positions):
                self._say(f'Lost the neuron {name.replace("_", " ")}', kind='pruned')
            self._known = set(positions)

    def _why(self, name):
        """Why a neuron grew, in the brain's own record of it."""
        origin = getattr(getattr(self.sim.brain, 'ledger', None), 'origins', {}).get(name)
        label = name.replace('_', ' ')
        if origin is None:
            return f'Grew the neuron {label}'
        text = f'Grew the neuron {label}'
        if origin.deficit_summary:
            text += f': {origin.deficit_summary.rstrip(".")}'
        if origin.remedy:
            text += f'. It is there to {origin.remedy.rstrip(".")}'
        return text + '.'

    def step(self, ticks=1):
        with self._lock:
            for _ in range(max(1, min(int(ticks), 100000))):
                self._one_tick()

    def _loop(self):
        while not self._closed:
            if not self.running:
                time.sleep(0.05)
                continue
            began = time.monotonic()
            speed = self.speed
            batch = max(1, speed // 20)             # about twenty batches a second
            with self._lock:
                before = self.sim.tick
                if speed:
                    for _ in range(batch):
                        self._one_tick()
                else:
                    while time.monotonic() - began < 0.04:
                        for _ in range(50):
                            self._one_tick()
                done = self.sim.tick - before
            # A batch of `batch` ticks should take batch/speed seconds; flat
            # out, only long enough to let a reader in.
            wait = (batch / speed - (time.monotonic() - began)) if speed else 0.002
            if wait > 0:
                time.sleep(wait)
            spent = time.monotonic() - began
            if spent > 0:
                self.ticks_per_second = 0.7 * self.ticks_per_second + 0.3 * (done / spent)

    # ------------------------------------------------------------ steering
    def control(self, request):
        """Carry out one instruction from the page. Returns what to tell it."""
        from headless.headless_trainer import TRAINING_SCENARIOS
        from src.portable_brain import TrainingConfig
        do = request.get('do')
        with self._lock:
            if do == 'run':
                self.running = True
            elif do == 'pause':
                self.running = False
            elif do == 'step':
                self.running = False
                self.step(request.get('ticks', 1))
            elif do == 'speed':
                speed = int(request.get('speed', 10))
                if speed not in SPEEDS:
                    raise ValueError(f'speed must be one of {SPEEDS}')
                self.speed = speed
            elif do == 'intervene':
                kind = request.get('kind')
                if kind not in INTERVENTIONS:
                    raise ValueError(f'intervention must be one of {INTERVENTIONS}')
                # The simulation's own path for an outside event: it drops any
                # credit the squid's last action was waiting on, so nothing
                # the experimenter does is learned as something it did.
                self.sim._execute_event({'type': kind})
                self._say(f'You intervened: {kind}. Not counted as anything it did.', kind='intervention')
            elif do == 'reset':
                config = TrainingConfig()
                seed = request.get('seed')
                config.seed = int(seed) if seed not in (None, '') else None
                config.blank = bool(request.get('blank'))
                config.learning_enabled = bool(request.get('learning', True))
                scenario = request.get('scenario') or None
                if scenario and scenario not in TRAINING_SCENARIOS:
                    raise ValueError(f'unknown scenario: {scenario}')
                self.running = False
                self._brain_path, self._scenario = None, scenario
                self._build(config)
                self._say('Started again' + (f' with seed {config.seed}' if config.seed is not None else '')
                          + (', from a blank brain' if config.blank else '')
                          + ('' if config.learning_enabled else ', with learning off'))
            elif do == 'load':
                brain = request.get('brain')
                if not isinstance(brain, dict):
                    raise ValueError('that is not a brain file')
                self.running = False
                if not self.sim.brain.load_brain(brain):
                    raise ValueError('the trainer could not read that brain')
                self._known = set(self.sim.brain.positions)
                self._say(f'Loaded a brain of {len(self._known)} neurons')
            else:
                raise ValueError(f'unknown instruction: {do}')
            return self.snapshot()

    # ------------------------------------------------------------- reading
    def snapshot(self):
        from headless.headless_trainer import TRAINING_SCENARIOS
        from src import brain_constants as constants
        with self._lock:
            sim, brain, squid = self.sim, self.sim.brain, self.sim.squid
            innate = set(getattr(brain, 'innate_neurons', ()) or ())

            def kind(name):
                if name in constants.ACTION_NEURONS:
                    return 'action'
                if name in constants.CORE_STAT_NEURONS:
                    return 'drive'
                if name not in innate:
                    return 'grown'
                return 'sense'

            def number(value):
                if isinstance(value, bool):
                    return 100.0 if value else 0.0
                try:
                    return round(float(value), 2)
                except (TypeError, ValueError):
                    return 0.0
            state = squid.get_state_dict()
            stats = {key: value for key, value in sim.stats.items()
                     if isinstance(value, (int, float)) and not isinstance(value, bool)}
            return {
                'tick': int(sim.tick),
                'running': self.running,
                'speed': self.speed,
                'speeds': list(SPEEDS),
                'ticks_per_second': round(self.ticks_per_second, 1),
                'seed': self.config.seed,
                'blank': bool(getattr(self.config, 'blank', False)),
                'learning': bool(self.config.learning_enabled),
                'scenario': self._scenario,
                'scenarios': {key: s.description for key, s in TRAINING_SCENARIOS.items()},
                'squid': {
                    'personality': state.get('personality'),
                    'status': state.get('status'),
                    'drives': {name: number(state.get(name)) for name in DRIVES},
                    'is_sleeping': bool(state.get('is_sleeping')),
                    'is_startled': bool(state.get('is_startled')),
                    'position': [round(float(squid.x), 3), round(float(squid.y), 3)],
                },
                'world': {
                    'food': [[round(f['x'], 3), round(f['y'], 3)] for f in sim.food_items],
                    'plants': [[round(p['x'], 3), round(p['y'], 3)] for p in sim.plants],
                    'poop': len(sim.poop_items),
                },
                'neurons': [{'name': name, 'x': round(float(x), 1), 'y': round(float(y), 1),
                             'value': number(brain.state.get(name, 0.0)), 'kind': kind(name)}
                            for name, (x, y) in brain.positions.items()],
                'connections': [[src, dst, round(float(weight), 3)]
                                for (src, dst), weight in brain.weights.items()
                                if src in brain.positions and dst in brain.positions],
                'actions': dict(sorted(sim.stats.get('actions_selected', {}).items(),
                                       key=lambda item: -item[1])),
                'stats': stats,
                'log': list(self.log),
            }

    def brain_document(self):
        with self._lock:
            return self.sim.brain.export_brain()

    def close(self):
        self._closed = True
        self.running = False


def _handler(trainer):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'DosidicusTrainer'

        def log_message(self, *args):          # the trainer's own output is the log
            pass

        def _local(self):
            """Only this computer's own pages may talk to the trainer."""
            host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]')
            return host in ('127.0.0.1', 'localhost', '::1')

        def _send(self, status, body, content_type='application/json', extra=()):
            data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            for name, value in extra:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._local():
                return self._send(403, {'error': 'this trainer answers only to this computer'})
            path = self.path.split('?', 1)[0]
            if path in ('/', '/index.html'):
                return self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
            if path == '/state':
                return self._send(200, trainer.snapshot())
            if path == '/brain.json':
                name = f'trained_brain_tick{trainer.sim.tick}.json'
                return self._send(200, json.dumps(trainer.brain_document(), indent=1, default=str).encode('utf-8'),
                                  extra=[('Content-Disposition', f'attachment; filename="{name}"')])
            return self._send(404, {'error': 'nothing here'})

        def do_POST(self):
            if not self._local():
                return self._send(403, {'error': 'this trainer answers only to this computer'})
            # A page on another site cannot send JSON here without asking first.
            if 'application/json' not in (self.headers.get('Content-Type') or ''):
                return self._send(415, {'error': 'send JSON'})
            if self.path.split('?', 1)[0] != '/control':
                return self._send(404, {'error': 'nothing here'})
            try:
                length = int(self.headers.get('Content-Length') or 0)
                if length > 32 * 1024 * 1024:
                    return self._send(413, {'error': 'too large'})
                request = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(request, dict):
                    raise ValueError('send an object')
                return self._send(200, trainer.control(request))
            except (ValueError, TypeError, KeyError) as problem:
                return self._send(400, {'error': str(problem)})

    return Handler


def serve(port=8765, config=None, brain=None, scenario=None, ready=None):
    """Run the live trainer until interrupted. `ready(server, trainer)` is
    called once it is listening (the tests use it)."""
    trainer = LiveTrainer(config, brain=brain, scenario=scenario)
    server = ThreadingHTTPServer(('127.0.0.1', int(port)), _handler(trainer))
    server.daemon_threads = True
    address = f'http://127.0.0.1:{server.server_address[1]}/'
    print(f'\n🧪 Live trainer: open {address} in a web browser. Ctrl+C here stops it.\n')
    if ready is not None:
        ready(server, trainer)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        trainer.close()
        server.server_close()
    return trainer
