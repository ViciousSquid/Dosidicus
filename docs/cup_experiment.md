# The cup-and-food experiment

Three cups on the tank floor. Bait one where the squid can see it, shuffle them,
and the food ends up hidden under one. The squid swims to a cup. Lift it. If it
picked right, it eats.

That is the game — **Actions → Play: Cup & Food**. This document is about the
measurement underneath it, which is the reason the game exists.

A three-cup forced choice has a chance rate of exactly 1/3, so "did the squid
learn anything?" stops being an impression and becomes a number with an error
bar on it.

---

## The question, and the answer it got

**Can an unchanged Dosidicus brain learn to follow food it can no longer see?**

Two things were measured, and they came out differently.

| | measure | result |
|---|---|---|
| **Which cup** | does it go to the baited one more than the frozen control does? | **No.** Null in all ten seeds run; pooled +5.0 pp, p = 0.33. |
| **Drive under occlusion** | does it still *want* to eat once the food vanishes? | **Yes.** Pooled +19 pp, p < 0.001, measured in a frozen block. |

The squid does not learn *where* the food went. It does learn to go on wanting
it once it is gone.

### Which cup: no, and the reason is architectural

This was checked against the code *before* the experiment was built, because
the answer decides what the experiment is allowed to claim.

Everything the world writes into the network goes through
`BrainNeuronHooks.get_input_neuron_values()`, and every one of those values is a
**scalar with no spatial content**: `can_see_food` (is there food in the cone at
all), `plant_proximity`, `threat_level`, `external_stimulus`, and the state
flags. Everything the network can *do* is an action neuron from
`brain_constants.ACTION_NEURONS`, and none of those is directional either —
there is `act_eat`, and there is no `act_go_left`.

The squid's position does appear in the dict handed to `update_brain`, under
`position` — but it is a tuple, so `propagation.activation_of` returns `None`
for it and no synapse can read it.

So:

* the network **can** represent "there is food about" and "I want to eat", and
  plasticity can change how strongly it wants to — those are activations on
  neurons it has;
* the network **cannot** represent "the food is at the left cup". There is no
  input that differs between the three cups and no output that differs between
  going to one and going to another.

A representation the architecture cannot form is not one that experience can
teach it. The experiment therefore **predicted this null in advance** and was
built to measure it honestly rather than to avoid it.

The fix would be a positional sense and a directed action. That is exactly what
this experiment is forbidden to add, and exactly the finding worth reporting.

### Drive under occlusion: yes, and it survives freezing

How hard `act_eat` is driven while the food is hidden **is** an activation on an
existing neuron, reached through synapses the existing plasticity engine moves.
So this is where training can show — and it does.

Pooled over five seeds, in the **frozen** evaluation block, the learning arm's
food-seeking drive survives occlusion at **59%** of its with-food-in-sight level
against the learning-disabled control's **40%** (+19 pp, p < 0.001).

Note the control arm's own drive also rises from its no-information baseline
(26% → 40%, p < 0.001). Part of the effect is simply the protocol — a squid that
spends bait and shuffle phases looking at food is in a different state from one
that never saw any. That is precisely why the headline comparison is
**learning arm against frozen control**, both of which get the same protocol,
rather than against the baseline.

This is the full chain the experiment set out to demonstrate, and it runs
entirely on machinery that was already there:

> visible food → experience of its location → food hidden → the squid goes on
> seeking → a correct choice is eaten through `Squid.eat` → the ordinary
> positive consequence → measurable change in the weights, recorded in the
> provenance ledger → still measurable when learning is frozen.

---

## What the experiment may not do

* **No new neurons. No new sensors.** Not `food_under_cup`, not `cup_left`, not
  a hidden food-location sense, not anything whose purpose is to make this task
  learnable. `NoNewStructureTests` scans the source for them.
* **No concept of a cup, or of a choice.** The squid swims where its own network
  sends it. The experiment layer watches its ordinary position and calls the
  first cup it reaches its selection. The interpretation is ours.
* **`can_see_food` keeps its meaning.** While the food is under a cup it is not
  among the objects handed to the vision worker, so the sensor reads 0 by the
  existing code path — no special case, no second rule.
* **The ghost marker is the experimenter's.** It is drawn in the tank so you can
  see the ground truth, but like the cups it carries no `category`, so
  `extract_scene_objects` never hands it to the squid.
* **No second reward system.** A correct choice puts the same food item back in
  the world and the squid eats it with `Squid.eat` — the call a hand-fed squid
  gets, with the stat changes, the reflex and the memory a hand-fed squid gets.

---

## How a run is structured

Three blocks, each answering a different question:

1. **`naive` — the no-information baseline.** Same apparatus, same body, same
   wander, but the squid is never shown the bait. Nothing it does can beat 1 in
   3, so whatever this block scores is *what chance looks like here*. That is
   the number the other blocks are compared against, rather than a 33.3% taken
   on faith. Measured frozen.
2. **`train`** — the protocol with the squid free to learn from it.
3. **`eval`** — the protocol again with **plasticity frozen**
   (`RecordedSynapses.set_learning_frozen`, enforced in the one method every
   synaptic write goes through), so nothing measured can be something the squid
   picked up while being measured.

And a whole second arm: **the learning-disabled control**, the same protocol
from the same seed with plasticity frozen throughout. `eval` against that
control is the comparison the design turns on.

### Why the control arm is not optional

The apparatus gives points away. A squid spends the bait and shuffle phases
swimming *to* the baited cup, so when the food vanishes it is standing on the
answer — and a squid that simply picks the nearest cup scores well above 1/3
while knowing nothing whatever.

Two things address it:

* **the start-position rule** — the choice window opens only once the squid is
  clear of every cup (`start_clearance`, ~330px against a ~500px cup spacing),
  the same rule for all three cups. Trials are also reported split by whether
  that succeeded (`started_clear`), so the effect is measured rather than
  hidden;
* **the control arm** — whatever is left of the free gift is present in both
  arms, so only the *difference* counts as learning.

### Husbandry

Between trials — never inside one — the squid is let to sleep, fed if hungry,
and the tank cleaned. A trial is minutes of the squid's life and a run is dozens
of trials; without this, `HeadlessSquid` starves, never sleeps off its
sleepiness and (it has no anxiety decay at all) finishes every long run pinned
at 100 in a collapse that inhibits every voluntary action it has. That would
measure a distressed animal, not a learning one.

---

## Running it

```bash
# the paired design: learning arm and frozen control, same seed
python headless/cup_experiment_runner.py --seed 7 --naive 30 --train 50 --eval 50

# replicate across seeds and pool the trials -- see the warning below
python headless/cup_experiment_runner.py --seed 200 --seeds 5 --no-growth

# isolate plasticity from structural growth
python headless/cup_experiment_runner.py --no-growth

# vary the retention interval. At --delay 0 a good score means the squid coasted
# into the cup it was already heading for, not that it remembered.
python headless/cup_experiment_runner.py --delay 0
```

The instrument is the real engine, not a model of it: a real `HeadlessBrain`,
the real `decision_engine.select_action`, and `can_see_food` computed by calling
the shipping `VisionWorker._calculate_visibility` directly.

---

## One seed is one animal

This is the mistake that was actually made while building this experiment, and
it is worth stating plainly.

**Seed 7** produced a rise in occlusion persistence of **+22 percentage points at
p < 0.001** — a clean, significant, entirely convincing effect. It was nearly
written up as the result.

**Seed 2**, same code, produced **−1 point at p = 0.68**.

A single run of this experiment will hand you a significant effect roughly as
often as the significance level says it will. `--seeds N` exists for this: it
runs the paired design over N seeds and pools the trials (pooling trials, not
averaging p-values — a mean of p-values is not a p-value).

### The replication

```
python headless/cup_experiment_runner.py --seed 200 --seeds 5 --naive 30 --train 50 --eval 50 --no-growth
```

Five seeds, paired arms, trials pooled (pooling trials, not averaging p-values —
a mean of p-values is not a p-value). Eval block, learning arm vs frozen control:

| seed | which cup | drive under occlusion |
|---:|---|---|
| 200 | +3.5 pp (p=0.75) | +4 pp (p=0.17) |
| 201 | +16.2 pp (p=0.18) | **+15 pp (p<0.001)** |
| 202 | −11.3 pp (p=0.31) | **+29 pp (p<0.001)** |
| 203 | +9.1 pp (p=0.42) | **+26 pp (p<0.001)** |
| 204 | +9.9 pp (p=0.40) | **+22 pp (p<0.001)** |
| **pooled** | **+5.0 pp (p=0.33)** | **+19 pp (p<0.001)** |

An earlier, independent five-seed set (2, 7, 17, 43, 101) gave the same picture:
which cup never significant and negative in four of five; drive significant and
positive in three of five, never negative.

So: **which cup** is a solid null across ten seeds. **Drive** is positive in
seven of ten seeds individually, never negative in any, and strongly significant
pooled.

### A caution that was earned the hard way

Watch the per-seed column. Seed 200 shows +4 pp at p = 0.17 and seed 202 shows
+29 pp at p < 0.001 — same code, same settings.

While this experiment was being built, **seed 7** produced a drive effect of +22
pp at p < 0.001 and was nearly written up on its own. **Seed 2**, run next,
produced −1 pp at p = 0.68. Had the seeds come up in the other order, the
conclusion drawn from a single run would have been the opposite one.

One run of this experiment is one animal, and one animal is not a result. The
same caution applies in the other direction: the drive effect here is believable
because it pools over ten seeds, not because any one of them was convincing.

Watch the **pooled accuracy rows** too. The learning arm's eval block scores
41.5%, which is "above chance" against the 33.3% arithmetic at p = 0.015 — and
the *frozen control's* train block scores 40.9% at p = 0.021. Neither squid
learned anything about cups. That is the apparatus, and it is why every
conclusion here is drawn from learning-vs-control rather than from a distance
above 1/3.

---

## Where things live

| file | what it is |
|---|---|
| `src/cup_experiment.py` | Qt-free trial logic, trial records, and the scoring. The module docstring carries the architectural argument above. |
| `headless/cup_experiment_runner.py` | The reproducible instrument: brain, body, world, blocks, replication. |
| `src/cup_game_ui.py` | The game in the tank, and the observability panels. |
| `tests/test_cup_experiment.py` | Every control listed below. |
| `tests/test_cup_game_ui.py` | The claims that are only true if the game path is wired correctly. |

### The controls, as tests

Because the headline result is a null, and a null is worth nothing unless the
instrument can be shown to work:

* the cups are properly randomised — every arrangement occurs, each cup lands in
  each slot equally often, the bait is drawn uniformly;
* **the answer never reaches the squid** — the experiment never writes to brain
  state, and two worlds stepped through an identical trial differing *only* in
  which cup the food is under produce bit-identical brain state;
* `can_see_food` is 100 when the food is there to be seen and 0 when it is not,
  computed by the shipping vision worker;
* no new neuron or sensor — the sensor block is exactly
  `DEFAULT_INPUT_SENSORS`, the source contains none of the forbidden names, and
  any neuron that does appear has a recorded birth from neurogenesis;
* the baseline is 1/3, measured over ~180 no-information trials;
* no fixed strategy beats chance — "always the left cup", "always cup B", any of
  them;
* omissions are unrelated to the answer, which is what makes it sound to score
  accuracy over played trials;
* **the scoring can detect a real improvement** — fed a squid that does know the
  answer, it says so. A null from a dead instrument would mean nothing;
* the frozen evaluation really is frozen — not one weight moves, not one ledger
  event fires, not one neuron grows;
* the learning-disabled control could not have learned — every synaptic write
  was refused;
* measured differences correspond to real machinery — trials in the learning arm
  carry the weight deltas and provenance events that happened during them, and
  trials in the frozen arm carry none.
