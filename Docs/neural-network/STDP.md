# Spike-Timing-Dependent Plasticity

STDP is a **core feature of the engine**, in `src/stdp.py`, owned by
`src/plasticity.py`. It contributes to every weight change the squid makes
whether or not the STDP plugin is loaded.

Until v4.0 it did not, twice over:

* the plugin *was* the implementation. It monkey-patched
  `BrainWorker._perform_hebbian_learning` on the live instance and ran its own
  copy of the learning loop against a stale cache, so the squid's learning rule
  depended on whether a plugin happened to be enabled;
* in the core path, `compute_symmetric_stdp()` returns `(delta, direction)` and
  the caller coerced the tuple to a float. That raised, the exception was
  swallowed, and the spike-timing term was silently zero for every pair on
  every cycle. STDP was documented, implemented, wired in, and contributed
  nothing.

Both are fixed. The plugin is now an inspector over the engine's own learner.

## The rule

A spike is recorded when a neuron crosses `spike_threshold` on a rising edge,
outside its refractory period. For a directed pair, with
`Δt = t_post − t_pre`:

| Ordering | Δt | Effect |
|----------|----|--------|
| pre fires **before** post (causal) | > 0 | **LTP** — `+A₊ · exp(−Δt/τ₊)` |
| post fires **before** pre (acausal) | < 0 | **LTD** — `−A₋ · exp(Δt/τ₋)` |
| outside `time_window` | — | nothing |

Magnitude is boosted for new connections, for user-created neurons, and when
either endpoint is bursting.

The contribution is blended into the correlational rule at
`[Hebbian] stdp_weight` (default 0.4) — **only where spike timing actually has
an opinion**, because averaging its zero in on every other pair would drag
every estimate toward the middle.

## Eligibility traces: the third factor

Timing alone says which synapses were causally ordered. It does not say whether
the result was worth repeating. That is what eligibility traces are for.

`lay_eligibility_traces()` is called from `PlasticityEngine.observe()` **every
tick, while the spikes are fresh**. When an outcome lands — an action's
consequence window closing in `causal_learning.py`, or the caretaker feeding,
cleaning, medicating or startling the squid — `apply_reward_modulation()`
broadcasts its valence back along every live trace, and the resulting deltas go
through `BrainWidget.apply_weight_change()` tagged `causal_reward`.

This is what lets a consequence that arrives seconds after the action still
reach the synapses that produced it. It previously could not work at all: the
traces were laid on the 20-second commit cycle while the eligibility window was
2 seconds, so a trace and an outcome essentially never coincided. The window is
now 8 seconds, matched to `CausalConfig.outcome_window`.

## Seeing it

* **Learning tab** — LTP/LTD badges, the spike-timing delta and the blend, read
  from the provenance ledger.
* **Plugins → STDP → Control Panel** — live spikes, encodings, LTP/LTD counts,
  and sliders that tune the engine's real `STDPConfig`. The
  "Spike timing contributes to learning" toggle sets
  `plasticity.config.stdp_enabled`, which is the one switch the engine reads.
* **Knowledge tab** — the plain-English version, including which action's
  outcome reached a given synapse.

## Configuration

`STDPConfig` (see `src/stdp.py`) plus `[Hebbian] stdp_weight` in `config.ini`.
The learner works without Qt, so the headless trainer gets spike timing too.
