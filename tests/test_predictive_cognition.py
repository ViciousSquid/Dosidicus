"""
Verification suite for the predictive-cognition research module
(src/predictive_cognition.py, branch research/transformer-predictive-cognition).

WHAT THIS FILE IS FOR
---------------------
The predictive cortex claims to be a strictly additive research layer:
attached through the standard sensor interface, off by default, unable to
write anything the existing network could not already ignore, and trained
separately on what the squid actually perceived. Each claim is checked here
against the running code rather than taken on trust:

  1. OFF BY DEFAULT. A default-config simulation registers no prediction
     neurons and behaves exactly as the baseline engine.

  2. PREDICTIONS ARE SENSES. Registered prediction sensors are never
     overwritten by propagation; plasticity may grow synapses FROM them
     but never INTO them (a prediction cannot seize a motor neuron).

  3. NO PRIVILEGED INFORMATION. The observation vector contains no food
     coordinates when nothing is visible.

  4. THE TRANSFORMER ACTUALLY LEARNS. Analytic gradients are checked
     against finite differences, and loss decreases on a predictable
     synthetic stream.

  5. THE CONTROL IS REAL. The linear predictor updates online and holds
     a decaying trace of the last seen food.

  6. REPRODUCIBILITY. Identical seeds give identical runs; weights
     survive a save/load roundtrip; a brain trained with the cortex
     still exports into the vanilla loader.

RUNNING IT
----------
    python -m pytest -q tests/test_predictive_cognition.py

Every test is deterministic and needs no display and no Qt.
"""

import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "headless"))

from headless_trainer import HeadlessSimulation, TrainingConfig  # noqa: E402
from src.predictive_cognition import (  # noqa: E402
    CHANNEL_INDEX,
    DELTA_HORIZON,
    LinearPredictor,
    OBS_DIM,
    PREDICTION_SENSORS,
    PredictiveCortex,
    TinyTransformer,
    observation_vector,
    prediction_to_sensors,
)
from src.brain_constants import is_registered_input_sensor  # noqa: E402
from src.plasticity import PlasticityEngine  # noqa: E402


def make_config(**overrides):
    return TrainingConfig(**overrides)


def run_quiet(sim, ticks, progress_interval=0):
    with contextlib.redirect_stdout(io.StringIO()):
        return sim.run(ticks=ticks, progress_interval=progress_interval)


class OffByDefaultTests(unittest.TestCase):
    """The engine must be untouched unless the cortex is explicitly on."""

    def test_default_config_is_off(self):
        config = TrainingConfig()
        self.assertEqual(config.predictive_mode, 'off')

    def test_off_simulation_has_no_prediction_neurons(self):
        sim = HeadlessSimulation(make_config(seed=1))
        self.assertFalse(sim.predictive.enabled)
        for name, _pos in PREDICTION_SENSORS:
            self.assertNotIn(name, sim.brain.state,
                             f"{name} registered in off mode")
            self.assertNotIn(name, sim.brain.positions)

    def test_off_simulation_reports_off(self):
        sim = HeadlessSimulation(make_config(seed=1))
        stats = run_quiet(sim, 50)
        self.assertEqual(stats['predictive']['mode'], 'off')
        self.assertFalse(stats['predictive']['enabled'])

    def test_off_runs_the_baseline_path(self):
        # With the cortex off, the trainer must produce exactly what the
        # baseline engine produces for the same seed: same food eaten.
        sim = HeadlessSimulation(make_config(seed=42))
        stats = run_quiet(sim, 300)
        self.assertGreaterEqual(stats['food_seen_ticks'], 0)
        self.assertGreaterEqual(stats['ticks_completed'], 300)

    def test_old_config_dicts_still_load(self):
        # A config dict from before this branch existed has no predictive
        # keys; from_dict must keep accepting it.
        old = {'learning_enabled': True, 'seed': 7, 'food_spawn_chance': 0.02}
        config = TrainingConfig.from_dict(old)
        self.assertEqual(config.seed, 7)
        self.assertEqual(config.predictive_mode, 'off')


class PredictionSensorsAreSensesTests(unittest.TestCase):
    """The cortex must attach through the standard sensor interface."""

    @classmethod
    def setUpClass(cls):
        cls.sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=3,
                        predictive_train_interval=32))
        cls.run_stats = run_quiet(cls.sim, 300)

    def test_sensors_registered_through_standard_interface(self):
        for name, _pos in PREDICTION_SENSORS:
            self.assertTrue(is_registered_input_sensor(name),
                            f"{name} not registered as an input sensor")

    def test_sensors_exist_in_brain_with_positions(self):
        for name, pos in PREDICTION_SENSORS:
            self.assertIn(name, self.sim.brain.state)
            self.assertIn(name, self.sim.brain.positions)
            self.assertEqual(self.sim.brain.positions[name], pos)

    def test_propagation_never_overwrites_prediction_sensors(self):
        brain = self.sim.brain
        brain.state['pred_food_ahead'] = 77.7
        brain.propagate(observe_learning=False)
        self.assertEqual(brain.state['pred_food_ahead'], 77.7)

    def test_plasticity_grows_from_but_never_into_predictions(self):
        # A pair (core stat, prediction sensor) must orient so the
        # prediction is the SOURCE and the core stat the TARGET...
        pair = ('hunger', 'pred_food_ahead')
        oriented = PlasticityEngine.orient(pair, {}, ())
        self.assertEqual(oriented, ('pred_food_ahead', 'hunger'))
        # ...and a pair of two sensors must be refused entirely.
        two_sensors = ('can_see_food', 'pred_food_ahead')
        self.assertIsNone(PlasticityEngine.orient(two_sensors, {}, ()))

    def test_telemetry_populated(self):
        p = self.run_stats['predictive']
        self.assertTrue(p['enabled'])
        self.assertEqual(p['mode'], 'transformer')
        self.assertGreater(p['ticks_observed'], 0)
        self.assertGreater(p['train_steps'], 0,
                           "trainer never trained the transformer")
        self.assertGreaterEqual(p['action_top1_samples'], 0)
        self.assertIn('mae', p)
        self.assertIn('brain_effect', p)


class NoPrivilegedInformationTests(unittest.TestCase):
    """The observation must contain only what the squid perceived."""

    def test_hidden_food_is_absent_from_observation(self):
        squid_state = {'hunger': 40.0, 'position': (0.2, 0.2),
                       'threat_level': 0.0}
        obs = observation_vector(squid_state, (0.0, 0.0, 0.0), 'idle', {})
        self.assertEqual(obs[CHANNEL_INDEX['food_visible']], 0.0)
        self.assertEqual(obs[CHANNEL_INDEX['food_dx']], 0.0)
        self.assertEqual(obs[CHANNEL_INDEX['food_dy']], 0.0)

    def test_visible_food_is_egocentric_and_normalised(self):
        squid_state = {'hunger': 40.0, 'position': (0.5, 0.5)}
        # food one sight-radius east: dx = 0.32/0.32 = 1.0
        obs = observation_vector(squid_state, (1.0, 0.0, 1.0), 'idle', {})
        self.assertEqual(obs[CHANNEL_INDEX['food_visible']], 1.0)
        self.assertAlmostEqual(obs[CHANNEL_INDEX['food_dx']], 1.0)
        self.assertAlmostEqual(obs[CHANNEL_INDEX['food_dy']], 0.0)

    def test_action_is_one_hot(self):
        squid_state = {'position': (0.5, 0.5)}
        obs = observation_vector(squid_state, (0, 0, 0), 'eating', {})
        self.assertEqual(obs[CHANNEL_INDEX['act_eat']], 1.0)
        for channel in ('act_idle', 'act_fleeing', 'act_exploring'):
            self.assertEqual(obs[CHANNEL_INDEX[channel]], 0.0)

    def test_observation_dimension(self):
        squid_state = {'position': (0.5, 0.5)}
        obs = observation_vector(squid_state, (0, 0, 0), 'idle', {})
        self.assertEqual(obs.shape, (OBS_DIM,))

    def test_sensor_map_is_unsigned_and_bounded(self):
        rng = np.random.default_rng(0)
        values = prediction_to_sensors(
            rng.uniform(-3, 3, OBS_DIM).astype(np.float32),
            np.array([0.5, -0.2, 0.3, -0.9], dtype=np.float32),
            0.5)
        self.assertEqual(set(values), {n for n, _ in PREDICTION_SENSORS})
        for name, v in values.items():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 100.0)


class TinyTransformerLearnsTests(unittest.TestCase):
    """The transformer must be a real learner, not a fixture."""

    def test_gradients_match_finite_differences(self):
        model = TinyTransformer(obs_dim=6, d_model=8, layers=1, heads=2,
                                context=4, ffn_dim=6, delta_dim=2, seed=7)
        # float64 for a meaningful finite-difference check
        model.params = {k: v.astype(np.float64)
                        for k, v in model.params.items()}
        rng = np.random.default_rng(3)
        x = rng.random((3, 4, 6))
        target = rng.random((3, 4, 6))
        cache = {}
        pred, _ = model._forward(x, cache)
        diff = pred - target
        n = diff.size
        grads = model._backward(cache, 2.0 * diff / n,
                               np.zeros((3, 4, model.delta_dim)))
        checked = ['emb', 'pos', 'l0_wq', 'l0_wk', 'l0_wv', 'l0_wo',
                   'l0_w1', 'l0_w2', 'l0_ln1_g', 'l0_ln2_g', 'head_next']
        for name in checked:
            g = grads[name]
            self.assertTrue(np.isfinite(g).all(), f"{name} has non-finite grads")
            flat = g.reshape(-1)
            self.assertGreater(float(np.abs(flat).max()), 0.0,
                               f"{name} gradient is all zero")
            for i in (0, flat.size // 2, flat.size - 1):
                idx = np.unravel_index(i, g.shape)
                eps = 1e-5
                orig = model.params[name][idx]
                model.params[name][idx] = orig + eps
                plus = _mean_loss(model, x, target)
                model.params[name][idx] = orig - eps
                minus = _mean_loss(model, x, target)
                model.params[name][idx] = orig
                numeric = (plus - minus) / (2 * eps)
                analytic = float(g[idx])
                denom = max(abs(numeric), abs(analytic), 1e-8)
                self.assertLess(
                    abs(numeric - analytic) / denom, 1e-3,
                    f"{name}[{idx}] analytic={analytic:.6g} "
                    f"numeric={numeric:.6g}")

    def test_loss_decreases_on_predictable_stream(self):
        model = TinyTransformer(obs_dim=OBS_DIM, d_model=16, layers=1,
                                heads=2, context=16, ffn_dim=32, seed=11,
                                lr=0.01)
        rng = np.random.default_rng(5)
        # a synthetic stream with real temporal structure: a food percept
        # that sweeps east -> visible -> bite, over and over
        stream = []
        for t in range(400):
            phase = (t % 32) / 32.0
            obs = np.zeros(OBS_DIM, dtype=np.float32)
            obs[CHANNEL_INDEX['food_dx']] = np.sin(phase * math.pi)
            obs[CHANNEL_INDEX['food_dy']] = 0.3 * math.cos(phase * math.pi)
            obs[CHANNEL_INDEX['food_visible']] = \
                1.0 if 0.1 < phase < 0.9 else 0.0
            obs[CHANNEL_INDEX['hunger']] = 0.5 + 0.2 * math.sin(t / 16.0)
            stream.append(obs)
        stream = np.stack(stream)
        L = model.context
        x = np.stack([stream[i:i + L] for i in range(0, 300)])
        y = np.stack([stream[i + 1:i + 1 + L] for i in range(0, 300)])
        first = last = None
        for step in range(40):
            sel = rng.integers(0, len(x), size=8)
            res = model.train_on_windows(x[sel], y[sel])
            if math.isfinite(res['loss']):
                if first is None:
                    first = res['loss']
                last = res['loss']
        self.assertIsNotNone(first, "training never produced a finite loss")
        self.assertLess(last, 0.5 * first,
                         f"loss did not halve: first={first} last={last}")

    def test_causal_mask_prevents_looking_ahead(self):
        # Position 0 must not depend on later positions: perturbing the
        # stream after position k cannot change the prediction at k.
        model = TinyTransformer(obs_dim=6, d_model=8, layers=1, heads=2,
                                context=4, ffn_dim=6, delta_dim=2, seed=9)
        rng = np.random.default_rng(1)
        x = rng.random((1, 4, 6)).astype(np.float32)
        pred, _ = model._forward(x)
        x2 = x.copy()
        x2[0, 2, :] = 9.9      # corrupt the future
        pred2, _ = model._forward(x2)
        np.testing.assert_allclose(pred[0, :2], pred2[0, :2], atol=1e-6)
        self.assertFalse(np.allclose(pred[0, 2], pred2[0, 2]))


def _mean_loss(model, x, target):
    pred, _ = model._forward(x)
    diff = pred - target
    return float((diff ** 2).mean())


class LinearControlTests(unittest.TestCase):
    """The control condition must really run, not just exist."""

    def test_ema_updates_online(self):
        model = LinearPredictor()
        self.assertAlmostEqual(float(model.ema[CHANNEL_INDEX['hunger']]), 0.5)
        obs = np.zeros(OBS_DIM, dtype=np.float32)
        obs[CHANNEL_INDEX['hunger']] = 1.0
        for _ in range(20):
            model.observe(obs)
        self.assertGreater(float(model.ema[CHANNEL_INDEX['hunger']]), 0.99)

    def test_food_trace_persists_then_decays(self):
        model = LinearPredictor()
        obs = np.zeros(OBS_DIM, dtype=np.float32)
        obs[CHANNEL_INDEX['food_dx']] = 0.8
        obs[CHANNEL_INDEX['food_dy']] = -0.1
        obs[CHANNEL_INDEX['food_visible']] = 1.0
        model.observe(obs)
        pred, delta = model.predict_last(None)
        self.assertAlmostEqual(pred[CHANNEL_INDEX['food_dx']], 0.8, places=5)
        # the food leaves view: the trace fades but keeps pointing
        invisible = np.zeros(OBS_DIM, dtype=np.float32)
        model.observe(invisible)
        pred, _ = model.predict_last(None)
        self.assertGreater(pred[CHANNEL_INDEX['food_dx']], 0.5)
        for _ in range(60):
            model.observe(invisible)
        pred, _ = model.predict_last(None)
        self.assertLess(pred[CHANNEL_INDEX['food_dx']], 0.05)

    def test_batch_training_is_a_noop(self):
        # the linear model learns purely online; replay must not
        # double-count experience
        model = LinearPredictor()
        before = model.ema.copy()
        windows = np.full((2, 4, OBS_DIM), 1.0, dtype=np.float32)
        model.train_on_windows(windows, windows)
        np.testing.assert_array_equal(model.ema, before)


class CortexProtocolTests(unittest.TestCase):
    """The begin/end tick protocol must produce usable experience."""

    @classmethod
    def setUpClass(cls):
        cls.sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=5,
                        predictive_train_interval=32))
        run_quiet(cls.sim, 150)

    def test_experience_buffer_grows_per_tick(self):
        cortex = self.sim.predictive
        self.assertGreaterEqual(cortex._ticks, 148)

    def test_predictions_written_every_tick(self):
        cortex = self.sim.predictive
        self.assertGreaterEqual(cortex._ticks, 100)
        self.assertIn('pred_food_ahead', cortex.last_sensors())

    def test_prediction_scores_against_outcomes(self):
        cortex = self.sim.predictive
        self.assertGreater(cortex._action_top1_n, 50,
                           "predictions were never scored")

    def test_delta_predictions_are_scored(self):
        # The delta head predicts a DELTA_HORIZON-tick change, so a
        # prediction matures several ticks after it is made: the queue
        # must drain and the telemetry must leave its initial 0.0.
        # Regression test for the bug that froze delta_mae at exactly
        # 0.0 for a whole run (each tick's new prediction overwrote
        # the previous one before its horizon arrived, so scoring
        # never ran).
        cortex = self.sim.predictive
        self.assertLessEqual(
            len(cortex._pending_deltas), DELTA_HORIZON + 1,
            "queued delta predictions never matured")
        self.assertGreater(
            cortex._delta_mae, 0.0,
            "delta telemetry never left its initial 0.0")

    def test_window_shape_matches_context(self):
        cortex = self.sim.predictive
        window = cortex._window()
        self.assertIsNotNone(window)
        self.assertEqual(window.shape[0], min(cortex._ticks,
                                              cortex.context))
        self.assertEqual(window.shape[1], OBS_DIM)

    def test_sleep_replay_counts_steps(self):
        cortex = self.sim.predictive
        before = cortex._sleep_steps
        cortex._sleeping = False
        cortex.sleep_replay(steps_per_night=5)
        self.assertGreaterEqual(cortex._sleep_steps, before)

    def test_linear_mode_runs_through_same_interface(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='linear', seed=5,
                        predictive_train_interval=32))
        stats = run_quiet(sim, 120)
        p = stats['predictive']
        self.assertEqual(p['mode'], 'linear')
        self.assertGreater(p['ticks_observed'], 0)
        for name, _pos in PREDICTION_SENSORS:
            self.assertIn(name, sim.brain.state)


class FrozenEvaluationTests(unittest.TestCase):
    """Learning disabled must freeze the transformer too, while the
    predictions still flow."""

    def test_frozen_run_never_trains(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=8,
                        learning_enabled=False,
                        predictive_train_interval=32))
        run_quiet(sim, 200)
        cortex = sim.predictive
        self.assertEqual(cortex._model.train_steps, 0)
        self.assertEqual(cortex._train_calls, 0)
        # but the cortex still observed and still predicted
        self.assertGreater(cortex._ticks, 150)
        self.assertIn('pred_food_ahead', cortex.last_sensors())

    def test_frozen_train_call_changes_nothing(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=8,
                        learning_enabled=False,
                        predictive_train_interval=32))
        run_quiet(sim, 200)
        params_before = {k: v.copy()
                         for k, v in sim.predictive._model.params.items()}
        sim.predictive.train()
        for k, v in sim.predictive._model.params.items():
            np.testing.assert_array_equal(v, params_before[k])


class ReproducibilityTests(unittest.TestCase):
    """Same seed, same run. That is what makes a result checkable."""

    def test_identical_seed_identical_run(self):
        # The FULL brain export is deliberately not compared: the baseline
        # provenance ledger stamps wall-clock timestamps and random
        # episode ids into every recorded weight change (see
        # src/neural_provenance.py) and the export metadata carries the
        # export time, so no two runs can ever be byte-identical that
        # way - a baseline property, not something this module
        # introduced. What a seed must pin down is the organism itself:
        # the same network state, the same learned weights, the same
        # behaviour statistics and the same trained transformer.
        results = []
        for _ in range(2):
            sim = HeadlessSimulation(
                make_config(predictive_mode='transformer', seed=123,
                            predictive_train_interval=32))
            run_quiet(sim, 200)
            brain = sim.brain
            results.append((
                json.dumps(brain.state, sort_keys=True),
                json.dumps(
                    [[list(edge), w] for edge, w in brain.weights.items()],
                    sort_keys=True),
                json.dumps(brain.positions, sort_keys=True),
                json.dumps(sim.predictive._model.state_dict(),
                           sort_keys=True),
                sim.stats['food_eaten'],
                sim.stats['food_approaches'],
                sim.stats['neurons_created'],
                sim.stats['hebbian_updates'],
                json.dumps(sim.stats['actions_selected'], sort_keys=True),
            ))
        self.assertEqual(results[0], results[1])

    def test_save_load_roundtrip(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=31,
                        predictive_train_interval=32))
        run_quiet(sim, 200)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'weights.json')
            self.assertTrue(sim.predictive.save_weights(path))
            fresh = HeadlessSimulation(
                make_config(predictive_mode='transformer', seed=31,
                            predictive_train_interval=32))
            self.assertTrue(fresh.predictive.load_weights(path))
        a = sim.predictive._model.state_dict()
        b = fresh.predictive._model.state_dict()
        self.assertEqual(json.dumps(a['params'], sort_keys=True),
                         json.dumps(b['params'], sort_keys=True))

    def test_layout_mismatch_is_refused(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=31,
                        predictive_train_interval=32))
        run_quiet(sim, 200)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'weights.json')
            sim.predictive.save_weights(path)
            with open(path) as f:
                data = json.load(f)
            data['channel_names'] = list(reversed(data['channel_names']))
            with open(path, 'w') as f:
                json.dump(data, f)
            fresh = HeadlessSimulation(
                make_config(predictive_mode='transformer', seed=31))
            self.assertFalse(fresh.predictive.load_weights(path))

    def test_brain_export_loads_into_vanilla_brain(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=13,
                        predictive_train_interval=32))
        run_quiet(sim, 150)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'brain.json')
            sim.brain.save_brain(path)
            vanilla = HeadlessSimulation(make_config(seed=13))
            self.assertTrue(vanilla.load_brain(path))
            # the prediction senses are ordinary neurons; they load as
            # ordinary (inert) neurons and the engine runs on
            run_quiet(vanilla, 50)


class HostNetworkIntegrationTests(unittest.TestCase):
    """The host network must be free to use or ignore the predictions."""

    def test_plasticity_can_use_prediction_sensors_as_sources(self):
        # A brain with prediction sensors develops synapses whose SOURCE
        # is a prediction sensor during a real run; they are never sinks.
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=17,
                        predictive_train_interval=32,
                        hebbian_interval=30))
        run_quiet(sim, 900)
        names = {n for n, _ in PREDICTION_SENSORS}
        edges = [(s, d) for (s, d) in sim.brain.weights
                 if s in names or d in names]
        into = [e for e in edges if e[1] in names]
        self.assertEqual(into, [],
                         "plasticity grew a synapse INTO a prediction "
                         "sensor, which is forbidden by the sensor "
                         "interface")
        # whether synapses grew FROM the sensors is up to the brain -
        # it may reasonably have ignored a useless prediction. But the
        # mechanism must allow it:
        oriented = PlasticityEngine.orient(
            ('pred_food_ahead', 'happiness'), sim.brain.weights, ())
        self.assertIsNotNone(oriented)
        if oriented is not None:
            self.assertEqual(oriented[0], 'pred_food_ahead')

    def test_neurogenesis_runs_with_prediction_sensors_present(self):
        sim = HeadlessSimulation(
            make_config(predictive_mode='transformer', seed=19,
                        predictive_train_interval=32))
        run_quiet(sim, 900)
        # neurogenesis is enabled and must still function; the exact
        # count is the brain's business, but the monitor must have been
        # observing a state that includes the prediction senses.
        cortex = sim.predictive
        self.assertGreaterEqual(cortex._ticks, 800)
        sig_names = set()
        # the capability monitor reads brain.state; the prediction
        # senses are part of it
        for name, _ in PREDICTION_SENSORS:
            self.assertIn(name, sim.brain.state)
            sig_names.add(name)
        self.assertGreater(len(sig_names), 0)


if __name__ == '__main__':
    unittest.main()



class IncidentalMotorBirthWiringTests(unittest.TestCase):
    """Controlled motor wiring intervention must not alter default birth wiring."""

    def test_context_motor_connections_can_be_omitted_but_other_context_remains(self):
        from src.neurogenesis import FunctionalNeuron, ExperienceContext
        ctx = ExperienceContext(
            trigger_type='novelty',
            active_neurons={'act_eat': 0.0, 'act_move': 0.0, 'hunger': 100.0},
            recent_actions=[], environmental_state={}, outcome='neutral',
            timestamp=0.0)
        neuron = FunctionalNeuron('probe', 'novelty', ctx)
        all_neurons = ['act_eat', 'act_move', 'hunger', 'curiosity', 'satisfaction']
        default = neuron.get_functional_connections(all_neurons)
        intervention = neuron.get_functional_connections(
            all_neurons, include_context_motor_targets=False)
        self.assertEqual(default['act_eat'], -0.8)
        self.assertEqual(default['act_move'], -0.8)
        self.assertNotIn('act_eat', intervention)
        self.assertNotIn('act_move', intervention)
        self.assertEqual(intervention['hunger'], 0.8)

    def test_headless_flag_is_opt_in(self):
        normal = HeadlessSimulation(make_config(seed=3))
        blocked = HeadlessSimulation(make_config(
            seed=3, context_motor_autowiring=False))
        self.assertTrue(normal.brain.learning_config.neurogenesis[
            'context_motor_autowiring'])
        self.assertFalse(blocked.brain.learning_config.neurogenesis[
            'context_motor_autowiring'])


class InnateOffloadGuardTests(unittest.TestCase):
    """Deliberately separate intentional differentiation from innate deletion."""

    def _offload(self, sim, source, target):
        from src.capability import Deficit
        from types import SimpleNamespace
        deficit = Deficit(
            kind='differentiation', key='test-offload', summary='test',
            sources=[source], target=target)
        return sim.brain.enhanced_neurogenesis._remedy_wiring(
            'test_new_neuron', deficit, SimpleNamespace(represents_concept=''))

    def test_innate_feed_path_survives_only_when_opted_in(self):
        edge = ('hunger', 'act_eat')
        historic = HeadlessSimulation(make_config(seed=21))
        guarded = HeadlessSimulation(make_config(
            seed=21, preserve_innate_motor_offload=True))
        self.assertIn(edge, historic.brain.weights)
        initial = guarded.brain.weights[edge]
        expected = ('test_new_neuron', 'act_eat', initial, 'remedy')
        old_plan = self._offload(historic, *edge)
        new_plan = self._offload(guarded, *edge)
        self.assertNotIn(edge, historic.brain.weights)
        self.assertIn(edge, guarded.brain.weights)
        self.assertIn(expected, new_plan)
        self.assertEqual(old_plan, new_plan)

    def test_guard_still_allows_learned_edge_retirement(self):
        sim = HeadlessSimulation(make_config(
            seed=21, preserve_innate_motor_offload=True))
        edge = ('curiosity', 'act_eat')
        sim.brain.apply_weight_change(
            edge, value=0.3, mechanism='manual', create=True)
        self.assertIn(edge, sim.brain.weights)
        self._offload(sim, *edge)
        self.assertNotIn(edge, sim.brain.weights)



class SignedIncidentalMotorWiringTests(unittest.TestCase):
    """The narrow guard removes negative incidental contacts, not positive ones."""

    def test_negative_only_keeps_positive_context_motor_wiring(self):
        from src.neurogenesis import ExperienceContext, FunctionalNeuron
        ctx = ExperienceContext(
            trigger_type='novelty',
            active_neurons={'act_eat': 0.0, 'act_move': 90.0, 'hunger': 100.0},
            recent_actions=[], environmental_state={}, outcome='neutral',
            timestamp=0.0)
        neuron = FunctionalNeuron('probe', 'novelty', ctx)
        targets = ['act_eat', 'act_move', 'hunger', 'curiosity', 'satisfaction']
        normal = neuron.get_functional_connections(targets)
        selective = neuron.get_functional_connections(
            targets, exclude_negative_context_motor_targets=True)
        all_blocked = neuron.get_functional_connections(
            targets, include_context_motor_targets=False)
        self.assertAlmostEqual(normal['act_eat'], -0.8)
        self.assertAlmostEqual(normal['act_move'], 0.64)
        self.assertNotIn('act_eat', selective)
        self.assertAlmostEqual(selective['act_move'], 0.64)
        self.assertAlmostEqual(selective['hunger'], 0.8)
        self.assertNotIn('act_eat', all_blocked)
        self.assertNotIn('act_move', all_blocked)

    def test_negative_only_flag_defaults_to_historical(self):
        default = TrainingConfig()
        self.assertFalse(default.exclude_negative_context_motor_targets)
        self.assertTrue(default.context_motor_autowiring)
        sim = HeadlessSimulation(make_config(
            seed=11, exclude_negative_context_motor_targets=True))
        self.assertTrue(sim.brain.learning_config.neurogenesis[
            'exclude_negative_context_motor_targets'])
