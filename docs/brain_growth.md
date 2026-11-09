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

## Results: run 13 (the full 240k study, seed 11)

Run 13 (CI run on commit d2e8f412, 2026-11-09, 01:58-03:16 UTC,
published in `ci-logs/13/results/`) ran the full design above: off /
linear / transformer, seed 11, 240,000 ticks each, 4 world phases.
All three runs completed without truncation.

### The neuron curve

| | off | linear | transformer |
|---|---|---|---|
| final live neurons | 31 | 42 | 44 |
| grown neurons | 12 | 13 | 15 |
| grown by type (cap) | stress 5/5, novelty 6/6, reward 1/6, connector 0/10 | stress 5/5, novelty 2/6, reward 0/6, connector 6/10 | stress 5/5, novelty 6/6, reward 0/6, connector 4/10 |
| last birth | tick 1,000 | tick 1,000 | tick 1,500 |
| final synapses | 471 | 418 | 524 |

All growth happens in the first 1,500 ticks - inside the **east**
phase, inside the first ~6 sim-seconds of a 960-second life. From tick
1,500 to 240,000, through the west mirror, the fouling phase and the
retention phase, the live neuron count is a flat line in all three
conditions. The quick 6k-tick smoke test's early plateau was not an
artifact of a short life; the full 240k life confirms it. **The
west and fouling phases do not resume growth in any condition.**

### The monitor's decisions: verdict - a forbidden plateau

This is a **forbidden plateau**, by the criteria above:

* **Type caps bind.** The stress cap (5/5) binds in all three
  conditions; the novelty cap (6/6) binds in off and transformer. The
  global ceiling (100) is nowhere near it - 31 to 44 neurons - so the
  ceiling is not the limiter, the per-type caps are.
* **Open deficits persist.** At tick 240,000 every condition still
  carries 6-9 active, actionable deficits (anxiety:down, hunger:down,
  cleanliness:up, happiness:up, satisfaction:up, sleepiness:down, plus
  representation deficits in off and linear). Nothing about the
  plateau is "satisfied": the monitor is still asking for structure.
  The dominant one, `regulation:anxiety:down`, accounts for 19,100 of
  the 19,145 stand-downs in each condition, and its suggested type is
  stress - the cap that is full.
* **Cap-blocked births become cooldown.** The stand-down histogram's
  head is misleading: 18,825 of 19,145 stand-downs per condition cite
  "only Ns into the 60s growth cooldown", and only ~320 cite the caps
  directly ("already has 5 stress neurons; strengthened one instead").
  But the mechanism chains: when the stress cap blocks a birth the
  engine *strengthens* an existing stress neuron, and that growth
  action restarts the 60s cooldown - so every subsequent evaluation of
  the still-open anxiety deficit is declined for "cooldown". The
  cooldown citations are the caps' shadow, not an independent reason.
  The capability monitor wanted a sixth stress neuron for 239,000
  consecutive ticks and was structurally refused.

The mode differences are real but secondary: the transformer brain
grows more (15 vs 12/13) and - uniquely - keeps **weight churn** alive
after the last birth (91 Hebbian updates after tick 1,500, cumulative
updates rising 105 -> 196 across the west/fouling/retention phases;
off and linear are frozen at 106 and 78). Even so, the transformer
squid's food eaten does not rise after tick 2,250 (3 total, all in
east), and it never eats in west, fouling or retention.

### Behavioural failures, documented honestly

* **Feeding collapses after the east phase.** Food eaten per phase:
  off 0/0/0/0 (1 total, tick <1,000), linear 0/0/0/0 (1 total),
  transformer 2/0/0/0 (3 total). No squid eats a single meal in the
  west, fouling or retention phases - 180,000 ticks of starving next
  to food.
* **The drives never recover.** Mean anxiety and hunger sit at ~100
  and cleanliness at ~0 for the last three phases in all conditions;
  the off-mode squid spends 239,632 of 240,000 actions "exhausted".
  The growth machinery's whole premise - diagnose a deficiency and
  fix it - is visibly failing to fix anything here.
* **The fouling problem was never solved.** The cleanliness deficit
  (a genuinely new problem at tick 120k) stood down 20 times in each
  condition and produced zero births (the transformer's
  `filth_avoidance` neuron was born at tick 1,000, in east, before
  fouling began) and no behavioural adaptation.
* The known headless-engine limitation above (stress neurons don't
  mechanically damp anxiety in the headless trainer) explains *why*
  the anxiety deficit never closes - which is why the stress cap
  stays pinned. The plateau is forbidden, and the forbidding cap is
  full of neurons that cannot do their job in this engine.

### What run 13 settles

Growth does not stop because the brain is satisfied. It stops because
two type caps fill up in the first six sim-seconds while the monitor's
top deficit permanently requests exactly the capped type. The 6k
smoke test's "12-15 grown neurons, caps far from binding, churn
continues" picture did not survive the full run: caps **are** binding
(stress 5/5 everywhere, novelty 6/6 in off/transformer), churn
continues only in the transformer condition, and no new phase - west
mirror or fouling - resumes either. Next steps worth considering:
raise or remove the stress cap, or fix the headless anxiety-relief
loop, and re-run to see whether growth resumes when the deficit's
requested type is available again.
