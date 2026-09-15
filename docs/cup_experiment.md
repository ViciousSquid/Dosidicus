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
| **Which cup** | does it go to the baited one more than 1 in 3? | **No.** Null in every seed. |
| **Drive under occlusion** | does it still *want* to eat once the food vanishes? | **Suggestive, not reliable.** Positive in 3 of 5 seeds. |

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

### Drive under occlusion: the part that could move

How hard `act_eat` is driven while the food is hidden **is** an activation on an
existing neuron, reached through synapses the existing plasticity engine moves.
If training teaches the squid anything here, it can show — and in some runs it
does, substantially. It just does not replicate reliably. See the numbers below.

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

### The five-seed replication

`naive=30, train=50, eval=50, --no-growth`, eval block, learning arm vs frozen
control:

| seed | which cup | drive under occlusion | control arm's own drift |
|---:|---|---|---|
| 2 | −13.3 pp (p=0.24) | −1 pp (p=0.68) | +2 pp (p=0.85) |
| 7 | +16.0 pp (p=0.17) | **+10 pp (p<0.001)** | −1 pp (p=0.89) |
| 17 | −11.9 pp (p=0.28) | **+16 pp (p<0.001)** | −8 pp (p=0.43) |
| 43 | −7.4 pp (p=0.51) | **+11 pp (p<0.001)** | **+12 pp (p=0.02)** |
| 101 | −17.6 pp (p=0.13) | −0 pp (p=0.94) | +11 pp (p=0.12) |

**Which cup:** never significant, and the direction is *negative* in four seeds
out of five. A solid, consistent null.

**Drive:** positive and strongly significant in three seeds, absent in two,
never negative. Real enough to be worth reporting, not reliable enough to be
called a result. Note also seed 43, where the frozen control's *own* drive
drifted significantly — one false positive in five at a 5% threshold, which is
about what you would expect, and another reason not to trust a single run.

So the honest summary is: **the squid does not learn which cup. Its
food-seeking drive under occlusion may strengthen with training, but that
effect does not replicate reliably across seeds.**

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
