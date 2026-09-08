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

## Timing is measured in samples, not seconds

The brain is observed once per simulation tick — about once a second at 1x, and
far faster when the game is sped up or a headless run loops flat out. The
original constants were chosen for a 50 ms sampler, so with a 0.5 s window and
1 s ticks two neurons that fired one tick apart fell *outside* the window
entirely: spike timing could only ever see simultaneity, which carries no
ordering information at all, and how much STDP happened depended on how fast
the machine ran.

`SpikeTracker` therefore measures the cadence it is actually fed at, and
`window_samples` / `tau_samples` scale to it. "Pre fired one sample before post"
then means the same thing at any speed, on any machine.

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

Two neurons that fire on the *same* sample produce nothing: there is no
ordering information there, and the correlational rule already accounts for
co-activation.

The delta is computed for the **exact synapse being updated**, not for the pair
in whichever direction happens to be stronger. Asking `compute_symmetric_stdp`
returned the stronger of the two orderings — essentially always the causal,
positive one — and that value was then applied to whichever direction
`orient()` had chosen. So LTD never reached a weight at all, and LTP could be
applied backwards.

The contribution is blended into the correlational rule at
`[Hebbian] stdp_weight` (default 0.4) — **only where spike timing actually has
an opinion**, because averaging its zero in on every other pair would drag
every estimate toward the middle.

## Eligibility traces: the third factor

Timing alone says which synapses were causally ordered. It does not say whether
the result was worth repeating. That is what eligibility traces are for.

An eligibility trace is a low-pass record of **pre × post activity**: it says
"this connection was participating just now", which is what a delayed outcome
needs in order to find the synapses responsible. `lay_eligibility_traces()` is
called from `PlasticityEngine.observe()` every tick, and the sign of any spike
ordering is folded in where one exists.

When an outcome lands — an action's consequence window closing in
`causal_learning.py`, or the caretaker feeding, cleaning, medicating or
startling the squid — `apply_reward_modulation()` broadcasts its valence back
along every live trace, and the resulting deltas go through
`BrainWidget.apply_weight_change()` tagged `causal_reward`.

Three things had to be true before this worked at all, and none of them were:

* traces were laid on the 20-second commit cycle while the window was 2 seconds,
  so a trace and an outcome essentially never coincided. They are now laid every
  tick and the window is 8 seconds, matched to `CausalConfig.outcome_window`;
* eligibility was restricted to pairs that both crossed the spike threshold
  inside the timing window. Over 600 ticks of ordinary life the squid produced
  ten spikes, essentially none of them coincident, so **no outcome ever reached
  a synapse**. Eligibility is participation, which is both the textbook
  definition and one that actually happens;
* a reward *cleared* every trace it touched, so the first outcome to land
  consumed the eligibility of every concurrent behaviour and later outcomes
  found nothing. A trace is now consumed in proportion to the credit taken;
  what ends it is its own decay.

The modulation is a **learning rate**, scaled by the same constant the
correlational rule uses and diluted by how many synapses share the claim. A
fixed step per synapse made a single reward worth more than a hundred
plasticity commits.

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
