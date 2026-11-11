"""The headless trainer served live (headless/serve.py): one trainer, a page
in front of it."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from headless.serve import LiveTrainer, serve
from src.portable_brain import TrainingConfig


def _config(seed=3):
    config = TrainingConfig()
    config.seed = seed
    return config


def test_it_steps_the_real_trainer_and_reports_the_brain():
    trainer = LiveTrainer(_config())
    try:
        first = trainer.snapshot()
        assert first['tick'] == 0 and not first['running']
        trainer.step(200)
        after = trainer.snapshot()
        assert after['tick'] == 200
        assert {n['name'] for n in after['neurons']} >= {'hunger', 'anxiety', 'act_eat'}
        assert all(a in {n['name'] for n in after['neurons']} and b in {n['name'] for n in after['neurons']}
                   for a, b, _w in after['connections'])
        assert set(after['squid']['drives']) == {'hunger', 'happiness', 'cleanliness', 'sleepiness',
                                                 'satisfaction', 'anxiety', 'curiosity'}
        json.dumps(after)                                   # everything the page is sent is JSON
        # the brain it hands back is one the trainer itself reads
        assert trainer.sim.brain.load_brain(json.loads(json.dumps(trainer.brain_document(), default=str)))
    finally:
        trainer.close()


def test_the_same_seed_gives_the_same_run_as_the_command_line():
    """The page steers the trainer; it is not another trainer."""
    from headless.headless_trainer import HeadlessSimulation
    plain = HeadlessSimulation(_config(11))
    for plain.tick in range(300):
        plain._process_events()
        plain._simulation_step()
    live = LiveTrainer(_config(11))
    try:
        live.step(300)
        assert live.sim.brain.weights == plain.brain.weights
        assert set(live.sim.brain.positions) == set(plain.brain.positions)
    finally:
        live.close()


def test_an_intervention_is_never_credited_to_the_squid():
    trainer = LiveTrainer(_config())
    try:
        trainer.step(50)
        eaten = trainer.sim.stats['food_eaten']
        state = trainer.control({'do': 'intervene', 'kind': 'feed'})
        assert trainer.sim.stats['manual_feedings'] == 1
        assert trainer.sim.stats['food_eaten'] == eaten    # not something it did
        assert state['log'][-1]['kind'] == 'intervention'
        with pytest.raises(ValueError):
            trainer.control({'do': 'intervene', 'kind': 'set_state'})
        with pytest.raises(ValueError):
            trainer.control({'do': 'speed', 'speed': 7})
    finally:
        trainer.close()


def test_a_neuron_it_grows_is_logged_with_its_reason():
    trainer = LiveTrainer(_config())
    try:
        trainer.step(400)
        grown = [entry for entry in trainer.snapshot()['log'] if entry['kind'] == 'neuron']
        assert grown and all(entry['text'].startswith('Grew the neuron ') for entry in grown)
        state = trainer.control({'do': 'reset', 'seed': 5, 'blank': True, 'learning': False})
        assert state['tick'] == 0 and state['blank'] and not state['learning'] and state['seed'] == 5
        assert len(state['neurons']) == 8
    finally:
        trainer.close()


def test_the_page_is_served_to_this_computer_only():
    box = {}
    started = threading.Event()

    def ready(server, trainer):
        box['server'], box['trainer'] = server, trainer
        started.set()
    thread = threading.Thread(target=serve, kwargs={'port': 0, 'config': _config(), 'ready': ready}, daemon=True)
    thread.start()
    assert started.wait(20)
    server = box['server']
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        assert server.server_address[0] == '127.0.0.1'
        page = urllib.request.urlopen(base + '/', timeout=10).read().decode('utf-8')
        assert 'Dosidicus Trainer' in page
        assert json.loads(urllib.request.urlopen(base + '/state', timeout=10).read())['tick'] == 0

        def post(body, headers):
            request = urllib.request.Request(base + '/control', data=body, headers=headers, method='POST')
            try:
                return urllib.request.urlopen(request, timeout=10).status
            except urllib.error.HTTPError as error:
                return error.code
        good = {'Content-Type': 'application/json'}
        assert post(b'{"do": "step", "ticks": 5}', good) == 200
        assert box['trainer'].sim.tick == 5
        assert post(b'do=run', {'Content-Type': 'application/x-www-form-urlencoded'}) == 415   # another site's form
        assert post(b'{"do": "run"}', dict(good, Host='elsewhere.example')) == 403             # a borrowed name
        assert post(b'{"do": "nonsense"}', good) == 400
        assert not box['trainer'].running
        brain = json.loads(urllib.request.urlopen(base + '/brain.json', timeout=10).read())
        assert 'neurons' in brain
    finally:
        server.shutdown()
        thread.join(10)
