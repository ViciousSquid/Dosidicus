"""
predictive_cognition.py - an optional temporal-prediction cortex.

RESEARCH MODULE (branch research/transformer-predictive-cognition).

The question this module exists to investigate: can a small transformer,
watching the same stream of experience the squid's own sensors report,
learn to predict what happens next - and can the existing plastic,
self-modifying network make use of those predictions without the
predictions ever becoming a second behaviour policy?

Design constraints, all of them load-bearing:

  * OPTIONAL AND OFF BY DEFAULT. With predictive_mode == 'off' nothing in
    this module runs: no sensors are registered, no NumPy work happens,
    and the engine behaves exactly as it did before this file existed.
    Every existing save, test and behaviour is untouched.

  * NO NEW DEPENDENCIES. The transformer is implemented in NumPy, which
    is already a core dependency. Nothing here imports Qt, torch, or any
    package outside the standard requirements. (A torch backend can be
    swapped in later behind the same interface; the interface is the
    point.)

  * PREDICTIONS ARE SENSES, NOT COMMANDS. The transformer's outputs are
    written into registered input sensors (brain_constants.
    register_input_sensor - the same interface plugins use), which means
    every existing mechanism treats them exactly as it treats any other
    sense organ:

      - forward propagation NEVER overwrites them (NON_PROPAGATED),
      - plasticity may grow synapses FROM them but never INTO them
        (is_learning_target), so the squid can learn to trust or ignore
        a prediction but a prediction cannot seize a motor neuron,
      - the capability monitor counts them in situation signatures, so
        neurogenesis remains free to grow new circuitry in response to
        them,
      - the causal learner may name them as antecedent cues.

    The original network retains full control of behaviour. If a
    prediction is useless, Hebbian decay and sleep pruning remove the
    synapses that listened to it.

  * NO PRIVILEGED INFORMATION. The observation vector is built only from
    what the squid has actually perceived this tick: its drives, its
    senses, its position, the relative direction of food it can CURRENTLY
    see, the action it took, and its own neural activations. Food the
    squid cannot see does not appear in the observation, at input time or
    at training time. Any object-permanence the transformer develops must
    come from remembering where food was last seen and integrating the
    squid's own motion since - which is the real thing, not a lookup.

  * SEPARATE LEARNING. The transformer is trained by gradient descent on
    its own prediction loss, on a ring buffer of the squid's recent
    experience. It does not touch the squid's synapses, and the squid's
    learning rules do not touch the transformer's weights. During sleep,
    the cortex runs extra offline replay training over the buffer - the
    transformer's analogue of the consolidation the rest of the brain
    already does. Training is skipped while learning_enabled is False
    (frozen evaluation), so evaluations stay frozen for the transformer
    too.

  * TRANSPARENCY. Prediction errors are measured against what actually
    happened next, per channel group, and reported alongside the effect
    the predictions had on the host network (which synapses grew from
    them). Nothing is claimed that is not measured.
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .brain_constants import register_input_sensor, is_registered_input_sensor

# ---------------------------------------------------------------------------
# The observation: the squid's experience, one tick at a time
# ---------------------------------------------------------------------------
# Channel groups. Values are 0..1. Everything here is something the squid
# perceived or did; nothing is read from the world behind its back.

DRIVE_CHANNELS = ('hunger', 'happiness', 'cleanliness', 'sleepiness',
                   'satisfaction', 'anxiety', 'curiosity')

FLAG_CHANNELS = ('is_sick', 'is_sleeping', 'is_eating', 'pursuing_food',
                 'is_fleeing', 'is_startled')

SENSE_CHANNELS = ('threat_level', 'can_see_food', 'plant_proximity',
                  'external_stimulus')

POSITION_CHANNELS = ('pos_x', 'pos_y')

# Egocentric food percept: the direction of the nearest food the squid
# can CURRENTLY see, normalised by the sight radius (so +1.0 = "one full
# sight-radius to the east", -1.0 = west), and whether it sees one at
# all. Zero when nothing is visible - not "the nearest food anywhere".
FOOD_CHANNELS = ('food_dx', 'food_dy', 'food_visible')

# What the squid did this tick, one-hot. The order is the decision
# engine's behaviour vocabulary for the headless body.
ACTION_CHANNELS = ('act_idle', 'act_exploring', 'act_eat', 'act_fleeing',
                   'act_sleeping', 'act_exhausted', 'act_sheltering',
                   'act_inking', 'act_playing')
ACTION_NAMES = ('idle', 'exploring', 'eating', 'fleeing', 'sleeping',
                'exhausted', 'approaching_plant', 'inking', 'playing')

# The squid's own motor activations, as its network computed them this
# tick (post-propagation). The transformer predicts its own future
# neural activity with these.
NEURAL_CHANNELS = ('neural_act_move', 'neural_act_eat', 'neural_act_flee',
                   'neural_act_ink', 'neural_act_play', 'neural_act_shelter',
                   'neural_act_rest', 'neural_act_collapse')
NEURAL_SOURCE_NEURONS = ('act_move', 'act_eat', 'act_flee', 'act_ink',
                         'act_play', 'act_shelter', 'act_rest',
                         'act_collapse')

# Drives whose 5-tick change the delta head predicts (tanh-scaled).
DELTA_CHANNELS = ('delta_hunger', 'delta_happiness', 'delta_anxiety',
                  'delta_satisfaction')
DELTA_SOURCES = ('hunger', 'happiness', 'anxiety', 'satisfaction')
DELTA_SCALE = 10.0     # a 10-point drive change in 5 ticks saturates tanh
DELTA_HORIZON = 5      # ticks ahead the delta head looks

CHANNEL_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ('drives', DRIVE_CHANNELS),
    ('flags', FLAG_CHANNELS),
    ('senses', SENSE_CHANNELS),
    ('position', POSITION_CHANNELS),
    ('food', FOOD_CHANNELS),
    ('action', ACTION_CHANNELS),
    ('neural', NEURAL_CHANNELS),
)

CHANNEL_NAMES: Tuple[str, ...] = tuple(
    name for _group, channels in CHANNEL_GROUPS for name in channels)
CHANNEL_INDEX = {name: i for i, name in enumerate(CHANNEL_NAMES)}
OBS_DIM = len(CHANNEL_NAMES)

GROUP_BOUNDS: Dict[str, Tuple[int, int]] = {}
for _group, _channels in CHANNEL_GROUPS:
    _start = CHANNEL_INDEX[_channels[0]]
    GROUP_BOUNDS[_group] = (_start, _start + len(_channels))


def observation_vector(squid_state: Dict[str, Any],
                      food_percept: Tuple[float, float, float],
                      action: str,
                      brain_state: Dict[str, Any]) -> np.ndarray:
    """Assemble the experience vector from what the squid perceived.

    `food_percept` is (dx, dy, visible) for the nearest food the squid
    can see, with dx/dy normalised by the sight radius (values in
    [-1, 1]), or (0, 0, 0). It is the caller's responsibility to derive
    it from the same perceptual test the can_see_food sensor uses.
    """
    obs = np.zeros(OBS_DIM, dtype=np.float32)
    for name in DRIVE_CHANNELS:
        obs[CHANNEL_INDEX[name]] = _unit(squid_state.get(name, 50.0))
    for name in FLAG_CHANNELS:
        obs[CHANNEL_INDEX[name]] = _flag(squid_state.get(name))
    for name in SENSE_CHANNELS:
        obs[CHANNEL_INDEX[name]] = _unit(squid_state.get(name, 0.0))
    if 'position' in squid_state:
        pos = squid_state['position']
        try:
            obs[CHANNEL_INDEX['pos_x']] = float(pos[0])
            obs[CHANNEL_INDEX['pos_y']] = float(pos[1])
        except (TypeError, ValueError, IndexError):
            pass
    dx, dy, visible = float(food_percept[0]), float(food_percept[1]), \
        float(food_percept[2] or 0.0)
    obs[CHANNEL_INDEX['food_dx']] = dx
    obs[CHANNEL_INDEX['food_dy']] = dy
    obs[CHANNEL_INDEX['food_visible']] = 1.0 if visible > 0.0 else 0.0
    action = str(action) if action else 'idle'
    idx = ACTION_NAMES.index(action) if action in ACTION_NAMES else 0
    obs[CHANNEL_INDEX[ACTION_CHANNELS[idx]]] = 1.0
    for channel, neuron in zip(NEURAL_CHANNELS, NEURAL_SOURCE_NEURONS):
        obs[CHANNEL_INDEX[channel]] = _unit(brain_state.get(neuron, 0.0))
    return obs


def _unit(value) -> float:
    try:
        return max(0.0, min(1.0, float(value) / 100.0))
    except (TypeError, ValueError):
        return 0.0


def _flag(value) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return 1.0 if float(value) > 50.0 else 0.0
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# The prediction senses: the transformer's readout, as the brain sees it
# ---------------------------------------------------------------------------
# All analogue, all 0-100, all registered through the standard sensor
# interface. Sensors rest at zero ("nothing to report"), so a prediction
# the transformer is not making reads as silence - the same convention as
# every other sense organ.

PREDICTION_SENSORS: Tuple[Tuple[str, Tuple[float, float]], ...] = (
    # (sensor name, layout position on the logical canvas)
    ('pred_food_ahead',     (120.0, 540.0)),
    ('pred_food_east',      (200.0, 540.0)),
    ('pred_food_west',      (280.0, 540.0)),
    ('pred_food_south',     (360.0, 540.0)),
    ('pred_food_north',     (440.0, 540.0)),
    ('pred_hunger_rise',    (520.0, 540.0)),
    ('pred_anxiety_rise',   (600.0, 540.0)),
    ('pred_reward_soon',    (680.0, 540.0)),
    ('pred_threat_soon',    (760.0, 540.0)),
    ('pred_uncertainty',    (840.0, 540.0)),
)

#: Percepts are pre-normalised by the sight radius, so predicted offsets
#: are already in [-1, 1] and map straight onto the 0..100 sensor range.


def prediction_to_sensors(pred_next: np.ndarray,
                          pred_delta: np.ndarray,
                          uncertainty: float) -> Dict[str, float]:
    """Translate the transformer's readout into sensor activations."""
    values: Dict[str, float] = {}
    ahead = float(np.clip(pred_next[CHANNEL_INDEX['food_visible']], 0.0, 1.0))
    values['pred_food_ahead'] = 100.0 * ahead
    dx = float(pred_next[CHANNEL_INDEX['food_dx']])
    dy = float(pred_next[CHANNEL_INDEX['food_dy']])
    values['pred_food_east'] = 100.0 * float(np.clip(max(0.0, dx), 0.0, 1.0))
    values['pred_food_west'] = 100.0 * float(np.clip(max(0.0, -dx), 0.0, 1.0))
    values['pred_food_south'] = 100.0 * float(np.clip(max(0.0, dy), 0.0, 1.0))
    values['pred_food_north'] = 100.0 * float(np.clip(max(0.0, -dy), 0.0, 1.0))
    if pred_delta is not None and len(pred_delta) >= 4:
        values['pred_hunger_rise'] = 100.0 * max(0.0, float(pred_delta[0]))
        values['pred_anxiety_rise'] = 100.0 * max(0.0, float(pred_delta[2]))
        reward = 0.5 * (float(pred_delta[1]) + float(pred_delta[3]))
        values['pred_reward_soon'] = 100.0 * max(0.0, reward)
    else:
        values['pred_hunger_rise'] = 0.0
        values['pred_anxiety_rise'] = 0.0
        values['pred_reward_soon'] = 0.0
    values['pred_threat_soon'] = 100.0 * float(np.clip(
        pred_next[CHANNEL_INDEX['is_startled']], 0.0, 1.0))
    values['pred_uncertainty'] = 100.0 * float(np.clip(uncertainty, 0.0, 1.0))
    return {name: round(max(0.0, min(100.0, v)), 4)
            for name, v in values.items()}


# ---------------------------------------------------------------------------
# A tiny transformer, in NumPy
# ---------------------------------------------------------------------------
# Decoder-only, causal self-attention: 2 layers, 4 heads, 64-dim by
# default. Every position predicts the experience one tick ahead, so a
# window of L ticks carries L supervised examples per forward pass. A
# second head predicts the tanh-scaled 5-tick change of four drives.

_GELU_C = math.sqrt(2.0 / math.pi)
_GELU_A = 0.044715


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(_GELU_C * (x + _GELU_A * x ** 3)))


def _gelu_grad(x: np.ndarray, dout: np.ndarray) -> np.ndarray:
    u = _GELU_C * (x + _GELU_A * x ** 3)
    t = np.tanh(u)
    dgelu = 0.5 * (1.0 + t) + 0.5 * x * (1.0 - t * t) * _GELU_C * (1.0 + 3.0 * _GELU_A * x * x)
    return dout * dgelu


def _softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - x.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


class _LayerNormParam:
    __slots__ = ('g', 'b')

    def __init__(self, dim: int, rng: np.random.Generator):
        self.g = np.ones(dim, dtype=np.float32)
        self.b = np.zeros(dim, dtype=np.float32)


class TinyTransformer:
    """A causal transformer over experience windows, trained with AdamW.

    float32 throughout; parameter dicts are flat {name: ndarray} so they
    serialise to plain JSON lists without pickle.
    """

    def __init__(self, obs_dim: int = OBS_DIM,
                 d_model: int = 64, layers: int = 2, heads: int = 4,
                 context: int = 32, ffn_dim: int = 128,
                 delta_dim: int = len(DELTA_CHANNELS),
                 seed: Optional[int] = None, lr: float = 3e-3):
        assert d_model % heads == 0
        self.obs_dim = obs_dim
        self.d_model = d_model
        self.layers = layers
        self.heads = heads
        self.d_head = d_model // heads
        self.context = context
        self.ffn_dim = ffn_dim
        self.delta_dim = delta_dim
        self.lr = lr
        rng = np.random.default_rng(seed)
        self.rng = rng
        p: Dict[str, np.ndarray] = {}
        p['emb'] = self._init(rng, (obs_dim, d_model))
        p['pos'] = np.zeros((context, d_model), dtype=np.float32)
        for l in range(layers):
            pre = f'l{l}'
            p[f'{pre}_ln1_g'] = np.ones(d_model, dtype=np.float32)
            p[f'{pre}_ln1_b'] = np.zeros(d_model, dtype=np.float32)
            p[f'{pre}_wq'] = self._init(rng, (d_model, d_model))
            p[f'{pre}_wk'] = self._init(rng, (d_model, d_model))
            p[f'{pre}_wv'] = self._init(rng, (d_model, d_model))
            p[f'{pre}_wo'] = self._init(rng, (d_model, d_model))
            p[f'{pre}_bq'] = np.zeros(d_model, dtype=np.float32)
            p[f'{pre}_bk'] = np.zeros(d_model, dtype=np.float32)
            p[f'{pre}_bv'] = np.zeros(d_model, dtype=np.float32)
            p[f'{pre}_bo'] = np.zeros(d_model, dtype=np.float32)
            p[f'{pre}_ln2_g'] = np.ones(d_model, dtype=np.float32)
            p[f'{pre}_ln2_b'] = np.zeros(d_model, dtype=np.float32)
            p[f'{pre}_w1'] = self._init(rng, (d_model, ffn_dim))
            p[f'{pre}_w2'] = self._init(rng, (ffn_dim, d_model))
            p[f'{pre}_b1'] = np.zeros(ffn_dim, dtype=np.float32)
            p[f'{pre}_b2'] = np.zeros(d_model, dtype=np.float32)
        p['lnf_g'] = np.ones(d_model, dtype=np.float32)
        p['lnf_b'] = np.zeros(d_model, dtype=np.float32)
        p['head_next'] = self._init(rng, (d_model, obs_dim)) * 0.5
        p['b_next'] = np.zeros(obs_dim, dtype=np.float32)
        p['head_delta'] = self._init(rng, (d_model, delta_dim)) * 0.5
        p['b_delta'] = np.zeros(delta_dim, dtype=np.float32)
        self.params = p
        self._adam_m = {k: np.zeros_like(v) for k, v in p.items()}
        self._adam_v = {k: np.zeros_like(v) for k, v in p.items()}
        self._adam_t = 0
        self.train_steps = 0

    @staticmethod
    def _init(rng, shape: Tuple[int, ...]) -> np.ndarray:
        fan_in = shape[0]
        return (rng.standard_normal(shape) * (1.0 / math.sqrt(fan_in))
                ).astype(np.float32)

    # -- forward ------------------------------------------------------------
    def _forward(self, x: np.ndarray, cache: Optional[dict] = None):
        """x: (B, L, obs_dim) with L <= context. Returns (next, delta):
        (B, L, obs_dim) and (B, L, delta_dim), each position predicting
        from what precedes it."""
        B, L, _ = x.shape
        pos = self.params['pos'][self.context - L:]
        h = x @ self.params['emb'] + pos[None, :, :]
        if cache is not None:
            cache['x'] = x
            cache['pos_slice'] = self.context - L
            cache['h0'] = h
        for l in range(self.layers):
            h = self._block(l, h, cache)
        hf, lnf_cache = self._ln(h, self.params['lnf_g'],
                                self.params['lnf_b'])
        if cache is not None:
            cache['hf'] = hf
            cache['lnf'] = lnf_cache
        flat = hf.reshape(-1, self.d_model)
        next_logits = (flat @ self.params['head_next']
                       + self.params['b_next']).reshape(B, L, self.obs_dim)
        delta_logits = (flat @ self.params['head_delta']
                        + self.params['b_delta']).reshape(B, L, self.delta_dim)
        return next_logits, delta_logits

    def _block(self, l: int, h: np.ndarray, cache: Optional[dict]):
        B, L, _ = h.shape
        H, dh = self.heads, self.d_head
        pre = f'l{l}'
        a, ln1_cache = self._ln(h, self.params[f'{pre}_ln1_g'],
                                self.params[f'{pre}_ln1_b'])
        q = (a @ self.params[f'{pre}_wq'] + self.params[f'{pre}_bq'])
        k = (a @ self.params[f'{pre}_wk'] + self.params[f'{pre}_bk'])
        v = (a @ self.params[f'{pre}_wv'] + self.params[f'{pre}_bv'])
        q4 = q.reshape(B, L, H, dh).transpose(0, 2, 1, 3)
        k4 = k.reshape(B, L, H, dh).transpose(0, 2, 1, 3)
        v4 = v.reshape(B, L, H, dh).transpose(0, 2, 1, 3)
        scores = np.matmul(q4, k4.transpose(0, 1, 3, 2)) / math.sqrt(dh)
        mask = np.triu(np.ones((L, L), dtype=bool), k=1)
        scores = scores + np.where(mask, -1e9, 0.0).astype(np.float32)
        att = _softmax(scores)
        ctx4 = np.matmul(att, v4)              # (B, H, L, dh)
        ctx = ctx4.transpose(0, 2, 1, 3).reshape(B, L, self.d_model)
        o = ctx @ self.params[f'{pre}_wo'] + self.params[f'{pre}_bo']
        h1 = h + o
        m, ln2_cache = self._ln(h1, self.params[f'{pre}_ln2_g'],
                                self.params[f'{pre}_ln2_b'])
        z1 = m @ self.params[f'{pre}_w1'] + self.params[f'{pre}_b1']
        f = _gelu(z1)
        z2 = f @ self.params[f'{pre}_w2'] + self.params[f'{pre}_b2']
        h2 = h1 + z2
        if cache is not None:
            cache[f'{pre}_h_in'] = h
            cache[f'{pre}_ln1'] = ln1_cache
            cache[f'{pre}_a'] = a
            cache[f'{pre}_ctx'] = ctx
            cache[f'{pre}_q4'] = q4
            cache[f'{pre}_k4'] = k4
            cache[f'{pre}_v4'] = v4
            cache[f'{pre}_att'] = att
            cache[f'{pre}_h1'] = h1
            cache[f'{pre}_ln2'] = ln2_cache
            cache[f'{pre}_m'] = m
            cache[f'{pre}_z1'] = z1
            cache[f'{pre}_f'] = f
        return h2

    @staticmethod
    def _ln(x: np.ndarray, g: np.ndarray, b: np.ndarray, eps: float = 1e-5):
        mean = x.mean(axis=-1, keepdims=True)
        var = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
        std = np.sqrt(var + eps)
        xhat = (x - mean) / std
        out = xhat * g + b
        return out, (xhat, std)

    # -- backward -----------------------------------------------------------
    def _backward(self, cache: dict, d_next: np.ndarray,
                  d_delta: np.ndarray) -> Dict[str, np.ndarray]:
        grads: Dict[str, np.ndarray] = {k: np.zeros_like(v)
                                        for k, v in self.params.items()}
        B, L, _ = cache['x'].shape
        dhf = d_next @ self.params['head_next'].T \
            + d_delta @ self.params['head_delta'].T
        hf_flat = cache['hf'].reshape(-1, self.d_model)
        grads['head_next'] = hf_flat.T @ d_next.reshape(-1, self.obs_dim)
        grads['b_next'] = d_next.reshape(-1, self.obs_dim).sum(axis=0)
        grads['head_delta'] = hf_flat.T @ d_delta.reshape(-1, self.delta_dim)
        grads['b_delta'] = d_delta.reshape(-1, self.delta_dim).sum(axis=0)
        dh = self._ln_backward(dhf, cache['lnf'], self.params['lnf_g'],
                               grads, 'lnf_g', 'lnf_b')
        for l in reversed(range(self.layers)):
            dh = self._block_backward(l, dh, cache, grads)
        # embedding and positions
        x_flat = cache['x'].reshape(-1, self.obs_dim)
        grads['emb'] = x_flat.T @ dh.reshape(-1, self.d_model)
        pos_grad = dh.sum(axis=0)                    # (L, d)
        pg = grads['pos']
        pg[cache['pos_slice']:cache['pos_slice'] + L] += pos_grad
        return grads

    def _block_backward(self, l: int, dh2: np.ndarray, cache: dict,
                        grads: Dict[str, np.ndarray]) -> np.ndarray:
        pre = f'l{l}'
        B, L, _ = dh2.shape
        H, dh = self.heads, self.d_head
        # residual 2: h2 = h1 + z2
        dz2 = dh2
        grads[f'{pre}_w2'] += cache[f'{pre}_f'].reshape(-1, self.ffn_dim).T \
            @ dz2.reshape(-1, self.d_model)
        grads[f'{pre}_b2'] += dz2.reshape(-1, self.d_model).sum(axis=0)
        df = dz2 @ self.params[f'{pre}_w2'].T
        dz1 = _gelu_grad(cache[f'{pre}_z1'], df)
        grads[f'{pre}_w1'] += cache[f'{pre}_m'].reshape(-1, self.d_model).T \
            @ dz1.reshape(-1, self.ffn_dim)
        grads[f'{pre}_b1'] += dz1.reshape(-1, self.ffn_dim).sum(axis=0)
        dm = dz1 @ self.params[f'{pre}_w1'].T
        dh1 = self._ln_backward(dm, cache[f'{pre}_ln2'],
                                self.params[f'{pre}_ln2_g'], grads,
                                f'{pre}_ln2_g', f'{pre}_ln2_b')
        dh1 = dh1 + dh2                       # residual 2: h2 = h1 + z2
        # residual 1: h1 = h + o
        do = dh1
        dctx = do @ self.params[f'{pre}_wo'].T
        grads[f'{pre}_wo'] += cache[f'{pre}_ctx'].reshape(-1, self.d_model).T \
            @ do.reshape(-1, self.d_model)
        grads[f'{pre}_bo'] += do.reshape(-1, self.d_model).sum(axis=0)
        dctx4 = dctx.reshape(B, L, H, dh).transpose(0, 2, 1, 3)
        att = cache[f'{pre}_att']
        v4 = cache[f'{pre}_v4']
        q4 = cache[f'{pre}_q4']
        k4 = cache[f'{pre}_k4']
        d_att = np.matmul(dctx4, v4.transpose(0, 1, 3, 2))
        d_v4 = np.matmul(att.transpose(0, 1, 3, 2), dctx4)
        d_scores = att * (d_att - (d_att * att).sum(axis=-1, keepdims=True))
        d_scores = d_scores / math.sqrt(dh)
        d_q4 = np.matmul(d_scores, k4)
        d_k4 = np.matmul(d_scores.transpose(0, 1, 3, 2), q4)
        dq = d_q4.transpose(0, 2, 1, 3).reshape(B, L, self.d_model)
        dk = d_k4.transpose(0, 2, 1, 3).reshape(B, L, self.d_model)
        dv = d_v4.transpose(0, 2, 1, 3).reshape(B, L, self.d_model)
        a_flat = cache[f'{pre}_a'].reshape(-1, self.d_model)
        grads[f'{pre}_wq'] += a_flat.T @ dq.reshape(-1, self.d_model)
        grads[f'{pre}_bq'] += dq.reshape(-1, self.d_model).sum(axis=0)
        grads[f'{pre}_wk'] += a_flat.T @ dk.reshape(-1, self.d_model)
        grads[f'{pre}_bk'] += dk.reshape(-1, self.d_model).sum(axis=0)
        grads[f'{pre}_wv'] += a_flat.T @ dv.reshape(-1, self.d_model)
        grads[f'{pre}_bv'] += dv.reshape(-1, self.d_model).sum(axis=0)
        da = (dq @ self.params[f'{pre}_wq'].T
              + dk @ self.params[f'{pre}_wk'].T
              + dv @ self.params[f'{pre}_wv'].T)
        dh = self._ln_backward(da, cache[f'{pre}_ln1'],
                               self.params[f'{pre}_ln1_g'], grads,
                               f'{pre}_ln1_g', f'{pre}_ln1_b')
        return dh + dh1                       # residual 1: h1 = h + o

    def _ln_backward(self, dout: np.ndarray, ln_cache, g: np.ndarray,
                     grads: Dict[str, np.ndarray], gk: str, bk: str):
        xhat, std = ln_cache
        D = xhat.shape[-1]
        dxhat = dout * g
        grads[gk] += (dout * xhat).sum(axis=(0, 1))
        grads[bk] += dout.sum(axis=(0, 1))
        inner1 = dxhat.sum(axis=-1, keepdims=True)
        inner2 = (dxhat * xhat).sum(axis=-1, keepdims=True)
        dx = (dxhat - (inner1 + xhat * inner2) / D) / std
        return dx

    # -- training step --------------------------------------------------------
    def train_on_windows(self, windows: np.ndarray,
                         next_targets: np.ndarray,
                         delta_targets: Optional[np.ndarray] = None,
                         delta_mask: Optional[np.ndarray] = None,
                         lr: Optional[float] = None,
                         weight_decay: float = 0.01,
                         clip: float = 1.0) -> Dict[str, float]:
        """One AdamW step on a batch of experience windows.

        windows:      (B, L, obs_dim)      - experiences t-L+1 .. t
        next_targets: (B, L, obs_dim)     - the experience at each
                      position's NEXT tick (targets are pre-shifted by
                      the caller)
        delta_targets / delta_mask: (B, L, delta_dim) / (B, L, 1)
        """
        lr = lr if lr is not None else self.lr
        cache: dict = {}
        next_pred, delta_pred = self._forward(windows, cache)
        diff = next_pred - next_targets
        n_next = max(1, diff.size)
        loss_next = float((diff ** 2).sum() / n_next)
        d_next = 2.0 * diff / n_next
        if delta_targets is not None and delta_mask is not None:
            ddiff = delta_pred - delta_targets
            m = delta_mask.astype(np.float32)
            n_delta = max(1.0, float(m.sum()) * self.delta_dim)
            loss_delta = float(((ddiff ** 2) * m).sum() / n_delta)
            d_delta = 2.0 * ddiff * m / n_delta
        else:
            loss_delta = 0.0
            d_delta = np.zeros_like(delta_pred)
        grads = self._backward(cache, d_next.astype(np.float32),
                               d_delta.astype(np.float32))
        # gradient clip (global norm)
        total = math.sqrt(sum(float((g * g).sum()) for g in grads.values()))
        if total > clip and total > 0.0:
            scale = clip / total
            grads = {k: v * scale for k, v in grads.items()}
        if not (math.isfinite(loss_next) and math.isfinite(loss_delta)
                and math.isfinite(total)):
            return {'loss': float('nan'), 'skipped': 1.0}
        self._adam_t += 1
        self.train_steps += 1
        b1, b2, eps = 0.9, 0.999, 1e-8
        t = self._adam_t
        bc1 = 1.0 - b1 ** t
        bc2 = 1.0 - b2 ** t
        for k, grad in grads.items():
            m = self._adam_m[k]
            v = self._adam_v[k]
            m *= b1
            m += (1.0 - b1) * grad
            v *= b2
            v += (1.0 - b2) * (grad * grad)
            update = (m / bc1) / (np.sqrt(v / bc2) + eps)
            if k != 'pos':
                update = update + weight_decay * self.params[k]
            self.params[k] -= lr * update
        return {'loss': loss_next + loss_delta,
                'loss_next': loss_next, 'loss_delta': loss_delta}

    # -- inference ------------------------------------------------------------
    def predict_last(self, window: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict the next experience from the most recent window.

        window: (L, obs_dim), L <= context (may be shorter early in life).
        Returns (next_obs, delta) predictions for the tick after the last
        one in the window.
        """
        x = window[None, :, :]
        next_pred, delta_pred = self._forward(x)
        return next_pred[0, -1], delta_pred[0, -1]

    def state_dict(self) -> Dict[str, Any]:
        return {'format': 'predictive_cortex_weights', 'version': 1,
                'model': 'tiny_transformer',
                'obs_dim': self.obs_dim, 'd_model': self.d_model,
                'layers': self.layers, 'heads': self.heads,
                'context': self.context, 'ffn_dim': self.ffn_dim,
                'delta_dim': self.delta_dim,
                'train_steps': self.train_steps,
                'params': {k: np.asarray(v, dtype=np.float32).tolist()
                           for k, v in self.params.items()}}

    def load_state_dict(self, data: Dict[str, Any]) -> bool:
        if data.get('model') != 'tiny_transformer':
            return False
        if int(data.get('obs_dim', -1)) != self.obs_dim:
            return False
        params = data.get('params') or {}
        for k, v in params.items():
            if k not in self.params:
                continue
            arr = np.asarray(v, dtype=np.float32)
            if arr.shape != self.params[k].shape:
                return False
            self.params[k] = arr
        self._adam_m = {k: np.zeros_like(v) for k, v in self.params.items()}
        self._adam_v = {k: np.zeros_like(v) for k, v in self.params.items()}
        self.train_steps = int(data.get('train_steps', 0))
        return True


# ---------------------------------------------------------------------------
# The control condition: a simple non-transformer temporal predictor
# ---------------------------------------------------------------------------
# An exponentially smoothed per-channel model plus a decaying memory trace
# of the last food direction. It runs through the same interface, writes
# the same senses and reports the same telemetry, so any behavioural
# difference between it and the transformer is attributable to the
# sequence modelling, not to the plumbing.

class LinearPredictor:
    def __init__(self, obs_dim: int = OBS_DIM, context: int = 32,
                 seed: Optional[int] = None, lr: float = 0.0):
        self.obs_dim = obs_dim
        self.context = context
        self.ema = np.full(obs_dim, 0.5, dtype=np.float32)
        self.food_trace = np.zeros(2, dtype=np.float32)
        self.train_steps = 0
        self._alpha = 0.25

    def observe(self, obs: np.ndarray) -> None:
        """One tick of online exponential smoothing (called once per tick)."""
        self.ema = (1.0 - self._alpha) * self.ema + self._alpha * obs
        if obs[CHANNEL_INDEX['food_visible']] > 0.5:
            self.food_trace = np.array(
                [obs[CHANNEL_INDEX['food_dx']], obs[CHANNEL_INDEX['food_dy']]],
                dtype=np.float32)
        else:
            self.food_trace *= 0.9     # the memory fades without input

    def predict_last(self, window: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Persistence prediction: the smoothed present as the future."""
        pred = self.ema.copy()
        pred[CHANNEL_INDEX['food_dx']] = self.food_trace[0]
        pred[CHANNEL_INDEX['food_dy']] = self.food_trace[1]
        pred[CHANNEL_INDEX['food_visible']] = float(np.hypot(*self.food_trace) < 1.0)
        delta = np.zeros(len(DELTA_CHANNELS), dtype=np.float32)
        return pred, delta

    def train_on_windows(self, windows, next_targets,
                         delta_targets=None, delta_mask=None, **kwargs):
        # A smoothing model has no parameters to fit; it learns purely
        # online through observe(). Batch training is a no-op so that
        # replayed experience is not double-counted.
        self.train_steps += 1
        return {'loss': 0.0}

    def state_dict(self) -> Dict[str, Any]:
        return {'format': 'predictive_cortex_weights', 'version': 1,
                'model': 'linear_predictor',
                'obs_dim': self.obs_dim,
                'train_steps': self.train_steps,
                'params': {'ema': self.ema.tolist(),
                           'food_trace': self.food_trace.tolist()}}

    def load_state_dict(self, data: Dict[str, Any]) -> bool:
        if data.get('model') != 'linear_predictor':
            return False
        params = data.get('params') or {}
        ema = np.asarray(params.get('ema', []), dtype=np.float32)
        if ema.shape == self.ema.shape:
            self.ema = ema
        trace = np.asarray(params.get('food_trace', []), dtype=np.float32)
        if trace.shape == self.food_trace.shape:
            self.food_trace = trace
        self.train_steps = int(data.get('train_steps', 0))
        return True


# ---------------------------------------------------------------------------
# The cortex: the orchestrator the trainer talks to
# ---------------------------------------------------------------------------

class PredictiveCortex:
    """Owns the predictor, the experience buffer and the prediction senses.

    The trainer calls, in order per tick:

        begin_tick(tick, squid_state, food_percept)   # before propagation
        ... the network propagates and chooses an action ...
        end_tick(action, brain_state)                 # after the action

    begin_tick scores the previous prediction against what actually
    happened, appends the completed experience to the buffer, produces the
    prediction for THIS tick (from experience strictly before it), and
    writes the prediction senses. end_tick completes this tick's
    experience with the action taken and the network's own activations.

    train() runs offline gradient steps on windows sampled from the
    buffer; sleep_replay() runs extra steps while the squid sleeps. Both
    are called by the trainer only while learning is enabled.
    """

    def __init__(self, brain, config, owner: str = 'predictive_cortex'):
        self.brain = brain
        self.config = config
        mode = str(getattr(config, 'predictive_mode', 'off') or 'off').lower()
        self.mode = mode
        self.enabled = mode != 'off'
        if not self.enabled:
            self._model = None
            return

        self.context = int(getattr(config, 'predictive_context', 32) or 32)
        self.lr = float(getattr(config, 'predictive_lr', 3e-3) or 3e-3)
        seed = getattr(config, 'predictive_seed', None)
        if seed is None:
            seed = getattr(config, 'seed', None)
        self._rng = np.random.default_rng(seed)

        if mode == 'transformer':
            self._model: Any = TinyTransformer(
                context=self.context, lr=self.lr, seed=seed)
        elif mode == 'linear':
            self._model = LinearPredictor(context=self.context, seed=seed)
        else:
            raise ValueError(f"unknown predictive_mode '{mode}'")

        # The experience buffer. Kept as a list of complete experience
        # records so training windows are always contiguous.
        self._buffer: deque = deque(maxlen=4096)
        self._pending: Optional[Dict[str, Any]] = None
        self._pending_pred: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self._pending_delta: Optional[Tuple[np.ndarray, np.ndarray, int]] = None

        # telemetry
        self._ticks = 0
        self._train_calls = 0
        self._sleep_steps = 0
        self._sleeping = False
        self._sleep_budget = 0
        self._group_mae: Dict[str, float] = {g: 0.0 for g, _ in CHANNEL_GROUPS}
        self._group_mae_n = 0
        self._delta_mae = 0.0
        self._action_top1 = 0.0
        self._action_top1_n = 0
        self._uncertainty = 1.0
        self._last_prediction: Optional[np.ndarray] = None
        self._last_sensors: Dict[str, float] = {}
        self._last_observation: Optional[np.ndarray] = None
        self._inference_seconds = 0.0
        self._train_seconds = 0.0
        self._loss_ema = None

        self._register_senses(owner)

    # -- senses ---------------------------------------------------------------
    def _register_senses(self, owner: str) -> None:
        """Register the prediction senses through the standard interface."""
        for name, position in PREDICTION_SENSORS:
            if not is_registered_input_sensor(name):
                register_input_sensor(name, binary=False,
                                      position=position, owner=owner)
        for name, position in PREDICTION_SENSORS:
            self.brain.positions[name] = position
            self.brain.state.setdefault(name, 0.0)

    # -- the per-tick protocol --------------------------------------------------
    def begin_tick(self, tick: int, squid_state: Dict[str, Any],
                   food_percept: Tuple[float, float, float]) -> None:
        if not self.enabled:
            return
        # The experience of the PREVIOUS tick completed at its end_tick and
        # is the last record in the buffer. Score the prediction that was
        # made for it (at the previous begin_tick) against what actually
        # happened.
        if self._pending_pred is not None and self._buffer:
            self._score(self._buffer[-1])
        if self._pending_delta is not None and self._buffer:
            self._score_delta()
        # Capture the percept half of THIS tick's experience; the action
        # and the network's own activations complete it at end_tick.
        self._pending = {'squid_state': squid_state,
                         'food_percept': tuple(food_percept),
                         'tick': tick}
        # Predict this tick from experience strictly before it. The window
        # ends at the last complete experience, which is the tick before
        # this one - never this tick's own sensors.
        window = self._window()
        if window is not None and len(window) >= 2:
            t0 = time.perf_counter()
            pred_next, pred_delta = self._model.predict_last(window)
            self._inference_seconds += time.perf_counter() - t0
        else:
            pred_next = np.zeros(OBS_DIM, dtype=np.float32)
            pred_delta = np.zeros(len(DELTA_CHANNELS), dtype=np.float32)
        self._pending_pred = (pred_next, pred_delta)
        if window is not None and len(window) >= 2 and self._buffer:
            # The delta head predicts the drive change over the next
            # DELTA_HORIZON ticks, measured from the last complete
            # experience. Score it only once that future has actually
            # arrived (see _score_delta), never against an arbitrary
            # window of the past.
            self._pending_delta = (np.array(self._buffer[-1], copy=True),
                                   pred_delta,
                                   self._ticks + DELTA_HORIZON)
        self._last_prediction = pred_next
        self._write_sensors(pred_next, pred_delta)

    def end_tick(self, action: str, brain_state: Dict[str, Any]) -> None:
        if not self.enabled or self._pending is None:
            return
        obs = observation_vector(self._pending['squid_state'],
                                 self._pending['food_percept'],
                                 action, brain_state)
        self._buffer.append(obs)
        if hasattr(self._model, 'observe'):
            self._model.observe(obs)     # online EMA for the linear control
        self._ticks += 1
        self._last_observation = obs
        self._pending = None

    def _score(self, actual: np.ndarray) -> None:
        pred_next = self._pending_pred[0]
        total_sq = 0.0
        for group, channels in CHANNEL_GROUPS:
            lo, hi = CHANNEL_INDEX[channels[0]], CHANNEL_INDEX[channels[-1]] + 1
            err = float(np.abs(pred_next[lo:hi] - actual[lo:hi]).mean())
            self._group_mae[group] = self._group_mae.get(group, 0.0) * 0.98 + err * 0.02
        self._group_mae_n += 1
        overall = float(np.abs(pred_next - actual).mean())
        self._uncertainty = 0.98 * self._uncertainty + 0.02 * min(1.0, overall * 4.0)
        # action top-1
        a0, a1 = CHANNEL_INDEX[ACTION_CHANNELS[0]], CHANNEL_INDEX[ACTION_CHANNELS[-1]] + 1
        pred_action = int(np.argmax(pred_next[a0:a1]))
        true_action = int(np.argmax(actual[a0:a1]))
        hit = 1.0 if pred_action == true_action else 0.0
        n = self._action_top1_n
        self._action_top1 = (self._action_top1 * n + hit) / (n + 1)
        self._action_top1_n = n + 1
        # Delta scoring lives in _score_delta(): the delta head predicts a
        # DELTA_HORIZON-tick change, which only becomes observable
        # DELTA_HORIZON ticks after the prediction was made.

    def _score_delta(self) -> None:
        """Score the pending delta prediction once its horizon arrives.

        The prediction was conditioned on the last complete experience
        (buffer position due_at - DELTA_HORIZON); it is scored against the
        experience DELTA_HORIZON ticks later, and not before.
        """
        base, pred_delta, due_at = self._pending_delta
        if self._ticks < due_at:
            return
        actual = self._buffer[-1]
        drive_idx = [CHANNEL_INDEX[d] for d in DELTA_SOURCES]
        actual_delta = np.tanh(
            (actual[drive_idx] - base[drive_idx]) / DELTA_SCALE
        ).astype(np.float32)
        err = float(np.abs(pred_delta - actual_delta).mean())
        self._delta_mae = 0.98 * self._delta_mae + 0.02 * err
        self._pending_delta = None

    def _window(self) -> Optional[np.ndarray]:
        if not self._buffer:
            return None
        n = min(len(self._buffer), self.context)
        return np.stack([self._buffer[-i] for i in range(n, 0, -1)], axis=0)

    def _write_sensors(self, pred_next: np.ndarray, pred_delta: np.ndarray) -> None:
        values = prediction_to_sensors(pred_next, pred_delta, self._uncertainty)
        for name, value in values.items():
            self.brain.state[name] = value
        self._last_sensors = values

    # -- training ---------------------------------------------------------------
    def train(self, minibatches: int = 2, batch: int = 8) -> Dict[str, float]:
        """Offline training on sampled windows of recent experience.

        Separately trained: the squid's own learning rules are not
        involved, and the transformer's gradients do not touch the
        squid's synapses.
        """
        # A frozen evaluation (learning_enabled=False) freezes the
        # transformer too: no training step may change its weights while
        # the host network is being evaluated, even if asked directly.
        learning_on = bool(getattr(self.config, 'learning_enabled', True))
        if (not self.enabled or not learning_on
                or len(self._buffer) < self.context + DELTA_HORIZON + 1):
            return {'loss': 0.0, 'steps': 0}
        losses = []
        t0 = time.perf_counter()
        for _ in range(minibatches):
            windows, targets, delta_targets, delta_mask = self._sample(batch)
            res = self._model.train_on_windows(windows, targets,
                                               delta_targets, delta_mask,
                                               lr=self.lr)
            if 'loss' in res and math.isfinite(res['loss']):
                losses.append(res['loss'])
        self._train_seconds += time.perf_counter() - t0
        self._train_calls += 1
        mean_loss = float(np.mean(losses)) if losses else 0.0
        if self._loss_ema is None:
            self._loss_ema = mean_loss
        else:
            self._loss_ema = 0.9 * self._loss_ema + 0.1 * mean_loss
        return {'loss': mean_loss, 'steps': len(losses)}

    def sleep_replay(self, steps_per_night: int = 40) -> None:
        """Extra offline replay while the squid sleeps.

        The brain's own sleep consolidation replays the day's co-activations;
        the cortex uses the same quiet period to replay the day's experience
        through the transformer. Bounded per night so a long sleep cannot
        dominate the run.
        """
        if not self.enabled:
            return
        if not self._sleeping:
            self._sleeping = True
            self._sleep_budget = steps_per_night
        if self._sleep_budget > 0:
            res = self.train(minibatches=1)
            if res.get('steps'):
                self._sleep_steps += 1
                self._sleep_budget -= 1

    def on_wake(self) -> None:
        if getattr(self, '_sleeping', False):
            self._sleeping = False
            self._sleep_budget = 0

    def _sample(self, batch: int):
        n = len(self._buffer)
        hi = n - DELTA_HORIZON - 1     # need t+1 and t+5 after the window end
        if hi <= self.context:
            hi = n - 1
        starts = [int(self._rng.integers(0, max(1, hi - self.context)))
                  for _ in range(batch)]
        buf = list(self._buffer)
        windows, targets = [], []
        delta_targets, delta_mask = [], []
        for s in starts:
            w = np.stack(buf[s:s + self.context], axis=0)
            t = np.stack(buf[s + 1:s + 1 + self.context], axis=0)
            windows.append(w)
            targets.append(t)
            if s + self.context + DELTA_HORIZON <= n:
                base = buf[s + self.context - 1]
                future = buf[s + self.context - 1 + DELTA_HORIZON]
                d_target = np.tanh((future[[CHANNEL_INDEX[d] for d in DELTA_SOURCES]]
                                    - base[[CHANNEL_INDEX[d] for d in DELTA_SOURCES]]
                                    ) / DELTA_SCALE).astype(np.float32)
                delta_targets.append(np.broadcast_to(
                    d_target, (self.context, len(DELTA_CHANNELS))).copy())
                delta_mask.append(np.ones((self.context, 1), dtype=np.float32))
            else:
                delta_targets.append(np.zeros(
                    (self.context, len(DELTA_CHANNELS)), dtype=np.float32))
                delta_mask.append(np.zeros((self.context, 1), dtype=np.float32))
        return (np.stack(windows), np.stack(targets),
                np.stack(delta_targets), np.stack(delta_mask))

    # -- introspection ---------------------------------------------------------
    def last_prediction(self) -> Optional[np.ndarray]:
        return getattr(self, '_last_prediction', None)

    def last_sensors(self) -> Dict[str, float]:
        return dict(getattr(self, '_last_sensors', {}))

    def prediction_direction(self) -> Optional[Tuple[float, float]]:
        """The predicted food direction as a signed (x, y) vector, for
        scoring from OUTSIDE the squid (experiment analysis only - the
        squid itself only ever sees the unsigned senses)."""
        s = getattr(self, '_last_sensors', {})
        if not s:
            return None
        return (s.get('pred_food_east', 0.0) - s.get('pred_food_west', 0.0),
                s.get('pred_food_south', 0.0) - s.get('pred_food_north', 0.0))

    def get_stats(self) -> Dict[str, Any]:
        if not self.enabled:
            return {'mode': 'off', 'enabled': False}
        effect = self._brain_effect()
        return {
            'mode': self.mode,
            'enabled': True,
            'ticks_observed': self._ticks,
            'train_calls': self._train_calls,
            'train_steps': self._model.train_steps,
            'sleep_train_steps': self._sleep_steps,
            'loss_ema': self._loss_ema,
            'mae': dict(self._group_mae),
            'delta_mae': self._delta_mae,
            'action_top1': self._action_top1,
            'action_top1_samples': self._action_top1_n,
            'uncertainty': self._uncertainty,
            'inference_seconds': round(self._inference_seconds, 3),
            'train_seconds': round(self._train_seconds, 3),
            'brain_effect': effect,
            'sensor_values': dict(self._last_sensors),
        }

    def _brain_effect(self) -> Dict[str, Any]:
        """What the host network has done with the prediction senses."""
        weights = getattr(self.brain, 'weights', None) or {}
        names = {n for n, _ in PREDICTION_SENSORS}
        edges = [(src, dst, w) for (src, dst), w in weights.items()
                 if src in names or dst in names]
        from_pred = [(s, d, w) for s, d, w in edges if s in names]
        into_pred = [(s, d, w) for s, d, w in edges if d in names]
        strongest = sorted(from_pred, key=lambda e: -abs(e[2]))[:5]
        return {
            'synapses_from_predictions': len(from_pred),
            'synapses_into_predictions': len(into_pred),
            'total_abs_weight_from_predictions': round(
                sum(abs(w) for _, _, w in from_pred), 4),
            'strongest_synapses': [
                {'source': s, 'target': d, 'weight': round(float(w), 4)}
                for s, d, w in strongest],
        }

    # -- persistence ---------------------------------------------------------
    def save_weights(self, filepath: str) -> bool:
        if not self.enabled:
            return False
        try:
            data = self._model.state_dict()
            data['channel_names'] = list(CHANNEL_NAMES)
            with open(filepath, 'w') as f:
                json.dump(data, f)
            return True
        except (OSError, ValueError) as exc:
            print(f"⚠️  Could not save predictive weights: {exc}")
            return False

    def load_weights(self, filepath: str) -> bool:
        if not self.enabled:
            return False
        try:
            with open(filepath) as f:
                data = json.load(f)
            channels = data.get('channel_names')
            if channels is not None and list(channels) != list(CHANNEL_NAMES):
                print("⚠️  Predictive weights were trained on a different "
                      "observation layout; not loading.")
                return False
            ok = self._model.load_state_dict(data)
            if ok:
                print(f"✓ Loaded predictive weights ({self.mode}) "
                      f"from {filepath}")
            return ok
        except (OSError, ValueError, KeyError) as exc:
            print(f"⚠️  Could not load predictive weights: {exc}")
            return False

    def save_report(self, filepath: str) -> bool:
        try:
            with open(filepath, 'w') as f:
                json.dump(self.get_stats(), f, indent=2)
            return True
        except OSError as exc:
            print(f"⚠️  Could not save predictive report: {exc}")
            return False
