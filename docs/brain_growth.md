# Brain growth study: a forbidden plateau, or a satisfied one?

This branch's predictive-cognition line asked whether a small
transformer improves the squid's cognition (runs 6-9,
`docs/predictive_cognition.md`). The growth study asks a question
about the brain itself, independent of which cortex is attached:

> If the brain grows rapidly at first and then stops, **why** did it
> stop? A brain that stops growing because it is forbidden to is a
> resource limiter. A brain that stops growing because it no longer
> needs to - while it keeps learning through its existing synapses -
> is regulating its own structural growth according to its needs.

The distinction is only observable if we record the live neuron count
against simulation time **alongside everything the growth machinery
decides along the way**, in a life long enough for any early growth
spurt to have finished and been tested by new problems.

## What the engine already decides (mechanisms, from the code)

Neurogenesis v4.0 (`src/neurogenesis.py`, `src/capability.py`) is
capability-driven, not event-driven. Nothing grows because "something
happened"; structure is spent only on a diagnosed deficiency:

* The **CapabilityMonitor** diagnoses six deficit kinds from the live
  network: `representation` (a recurring situation no neuron
  distinguishes), `regulation` (a drive stuck outside its comfort band
  while corrective synapses are absent, saturated, or too weak),
  `expression` (the causal learner knows a cue-action-outcome link no
  pathway can act on), `differentiation` (one neuron forced to stand
  for two incompatible situations), `causal_differentiation` (two
  actions share credit and nothing separates them), and
  `connectivity` (an unreachable island).
* A deficit earns structure only when **persistent** (>=3
  observations, >=20 sim-seconds old), **severe** (>=0.35) and
  **unresolved** (its severity is not already falling - ordinary
  learning gets its chance first).
* **Permission to grow** is then bounded by:
  * per-type caps: stress 5, novelty 6, reward 6, connector 10 grown
    neurons;
  * a global ceiling of 100 neurons (this branch's headless config);
  * a 60 sim-second cooldown between growth actions (15s floor even
    for emergencies);
  * severity-1.0 emergencies may bypass the global ceiling, but never
    the type caps.
* **Cap reached is an answer, not a wall**: the engine deepens the
  best existing neuron of that type (strength multiplier, bounded at
  4.0x) instead of growing a duplicate, and records that it stood
  down for that reason.
* Crucially for this study, the engine keeps an **evidence trail**:
  `growth_log` (every birth, with the deficit that justified it),
  `stood_down` (every declined growth, with the engine's reason -
  cooldown, ceiling, or cap-deepening), and the monitor's `resolved`
  ledger (every deficit that closed, and why: new structure, or
  ordinary learning).

A known limitation, documented honestly: the anxiety-cap relief loop
(`update_neuron_activations`) is GUI-engine behaviour that the
headless trainer does not call, so headless stress neurons do not
mechanically damp anxiety. The growth study runs the same headless
engine as runs 6-9, so it shares this limitation.

## Run 10 design

Three conditions (off / linear / transformer, identical except the
predictive cortex, as in runs 6-9), **one seed each**, one long life of
**240,000 ticks** (10x the 24k of every previous run), in the runs-8/9
world (startle every 700 ticks, food 16 ticks later within sight,
ambient startles silenced, learning live throughout).

The world changes under the squid mid-life, so that "solving new
problems by modifying existing synapses rather than adding neurons" is
a measurement rather than an interpretation:

| phase | ticks | world |
|---|---|---|
| east | 0-60k | the runs-8/9 contingency, unchanged |
| west | 60k-120k | the same contingency mirrored: food lands 0.2 west |
| fouling | 120k-180k | east again, heavily fouled water (a genuinely new problem: cleanliness regulation) |
| retention | 180k-240k | clean water again: does the east behaviour survive? |

Telemetry, sampled every 250 ticks straight from the engine's own
bookkeeping: live neuron count, synapse count, grown tissue by type
against its cap, deepened-neuron count and total strength multiplier,
Hebbian updates, total weight-update churn, open and actionable
deficits, growth cooldown, feeding, and the drives. Births, stand-downs
and deficit resolutions are merged from the evidence trail with the
tick they occurred at. A 40-minute soft deadline per run guarantees
the study always publishes something, even if a condition runs slower
than budgeted.

Honest caveats: n=1 per condition - growth *dynamics*, not statistics;
a replication seed can follow. The growth engine is shared by all
three conditions, so any difference in growth trajectories between
conditions is attributable to what the cortex adds to the squid's
perceptual stream.

## What the verdict looks like

* **Forbidden plateau**: neuron count flat while type caps or the
  global ceiling are actually reached, and the stand-down log fills
  with ceiling/cap/cooldown reasons while actionable deficits persist.
* **Satisfied plateau**: neuron count flat with none of the bounds
  binding, no actionable deficits (or deficits closing on their own),
  while weight churn continues and behaviour keeps improving.
* **Strongest possible evidence**: a new-problem phase adapted to with
  zero new neurons - but continued synaptic churn and recovered
  behaviour.

## Results

Pending run 10; will be published from
`ci-logs/<run>/results/growth_results.json` with the live neuron-count
graph against simulation time, the capability monitor's decisions
overlaid, and the honest verdict - in either direction.
