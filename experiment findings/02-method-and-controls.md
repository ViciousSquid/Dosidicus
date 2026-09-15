# 02 — Method and controls

---

## The protocol

Per trial, in order:

1. **Bait** — one of three cups is baited at random. The food is a real
   `QGraphicsPixmapItem` in `TamagotchiLogic.food_items`, so the VisionWorker
   sees it exactly as it sees any other food. The phase ends when the squid has
   **actually seen it** (`can_see_food` reaching 100), not after a fixed count a
   wandering view cone might spend looking the other way, plus a dwell so it
   gets a proper look.
2. **Shuffle** — the cups are rearranged and the bait travels with its own cup,
   **still in view**. This is what makes a shell game solvable in principle
   rather than a pure guess.
3. **Hide** — the food leaves the world (below).
4. **Retention interval** — 20 ticks with nothing visible, plus a wait until the
   squid is clear of every cup (below).
5. **Choice** — the squid swims. The first cup it reaches is its selection.
6. **Reveal** — the chosen cup is lifted.
7. **Outcome** — if correct, the same food item goes back into the world and the
   squid eats it via `Squid.eat`.

The squid is never told it is playing, and is given no concept of a cup or of a
choice. It swims where its own network sends it; the experiment layer watches
its ordinary position and *interprets*.

## What "hidden" means, and why

Hiding removes the food from `logic.food_items` **and** from the scene, keeping
the item itself for the reveal.

That closes two channels, and both had to close:

| channel | what it would have leaked |
|---|---|
| the vision cone | `extract_scene_objects` is fed `food_items`; an item not in it is not among the objects to be seen, so `can_see_food` reads 0 **by the existing code path**, with no special case and no change to its meaning. |
| `DecisionEngine._nearest_food()` | reads `logic.food_items` **directly, not vision**. Had the food stayed in that list while hidden, `act_eat` winning would have steered the squid straight at the answer. This was the single most dangerous leak in the design and it is not a vision problem at all. |

A note on rigour: the food is *represented* as absent rather than as an opaque
object occluding a present one. For every downstream consumer these are
identical — nothing about the food reaches the squid's eyes or its movement
drives either way — and the alternative would have meant adding occlusion
geometry to the VisionWorker, i.e. changing the meaning of `can_see_food` in
order to study it. The claim that matters is tested directly: the ground truth
exists in the experiment layer while being absent from every neural input.

## Three blocks, three questions

| block | learning | question |
|---|---|---|
| `naive` | frozen | The squid is **never shown the bait**. Nothing it does can beat 1 in 3, so whatever this scores is what chance looks like *in this apparatus* — the geometry, the body, the wander and all. |
| `train` | **on** | The protocol, with the squid free to learn from it. |
| `eval` | frozen | The protocol again with plasticity frozen, so nothing measured can be something picked up while being measured. |

And a whole second arm: the **learning-disabled control**, the same protocol
from the same seed with plasticity frozen throughout.

## Why the control arm is not optional

**The apparatus gives points away.** A squid spends the bait and shuffle phases
swimming *towards* the baited cup, so when the food vanishes it is standing on
the answer. A squid that simply goes to the nearest cup then scores well above
1/3 while knowing nothing whatsoever.

Two things address it:

- **the start-position rule** — the choice window opens only once the squid is
  clear of *every* cup (~330 px against a ~500 px cup spacing), the same rule
  for all three. Trials are also recorded with a `started_clear` flag and scored
  split by it, so what remains is measured rather than hidden;
- **the control arm** — whatever free gift survives is present in *both* arms,
  so only the **difference** counts as learning.

This is why every conclusion in [`03-results.md`](03-results.md) is drawn from
learning-vs-control and not from a distance above 1/3. The data show why that
matters: in replication B the *frozen control's* own training block scored 40.9%,
"above chance" at p = 0.021. It had learned nothing at all.

## Scoring

Accuracy is **hits / committed**, not hits / trials. A trial the squid never
played is an *omission*, and scoring omissions as errors measures how often it
felt like swimming to a cup, not how often it swam to the right one — a squid
that plays 60% of trials and guesses would "score" 20% and look reliably *worse*
than chance.

Dropping omissions is legitimate only because the squid cannot know which cup is
baited, so whether it plays is independent of which answer would have been
right. That independence is **measured, not assumed**: `omission_bias()` reports
the play rate per baited slot, and the spread was 5–12% across runs.

Statistics are pure-Python, no SciPy: exact binomial tail, Wilson score interval
(not Wald — these blocks are small enough that a normal approximation runs off
the end of [0, 1]), pooled two-proportion z for block comparisons, and a seeded
permutation test for the drive measure (bounded activation, no reason to be
normal, and it needs no table).

## Husbandry

Between trials, never inside one: the squid is let to sleep, fed if hungry, and
the tank cleaned.

This is not a thumb on the scale, it is the difference between measuring a
learning animal and a dying one. A trial is minutes of the squid's life and a run
is dozens of trials. Left alone over that span `HeadlessSquid` starves, never
sleeps off its sleepiness, and — it has **no anxiety decay at all** — finishes
every long run pinned at anxiety 100, in an `act_collapse` state that inhibits
every voluntary action it has. Early runs did exactly this. See
[`04-what-went-wrong.md`](04-what-went-wrong.md).

## The instrument is the real engine

Not a model of it:

| component | what actually runs |
|---|---|
| vision | `VisionWorker._calculate_visibility`, **called directly**. It touches no `self`, so it runs unbound with no thread and no Qt loop — `can_see_food` is decided by the code the game ships, not by a second copy of the cone arithmetic that could drift. |
| decisions | `decision_engine.select_action` — the same function the squid uses, and the same one a squid visiting another tank uses. |
| learning | `HeadlessBrain`: PlasticityEngine + STDP + ConsolidationManager + EnhancedNeurogenesis + CausalLedger, untouched. |
| movement | modelled on `Squid.move_squid` — innate reflex at food it can **see**, else the decision's drive, else the same random walk (`p = 0.20` of turning, never back onto the current heading). |
| reward | `Squid.eat` in the game; the same stat changes headlessly. No second reward system anywhere. |

## Freezing

`RecordedSynapses.learning_frozen`, enforced inside `apply_weight_change` —
**the one method every synaptic write passes through**. A freeze applied there
covers Hebbian commits, STDP, the innate reflexes, sleep consolidation, pruning
and the wiring of a grown neuron alike, and nothing can route around it.
Freezing also switches off structural growth, because a network that can still
grow a neuron mid-measurement is still adapting.

Verified rather than asserted: across an evaluation block, the weight dict, the
ledger's change count and the neuron set are all **identical** before and after.

## The controls, as tests

`tests/test_cup_experiment.py` (44 tests) and `tests/test_cup_game_ui.py` (12).
Because the headline is a null, most of these exist to rule out the ways a null
could be an artefact.

| claim | how it is tested |
|---|---|
| the cups are properly randomised | every arrangement occurs; each cup lands in each slot equally often; the bait is drawn uniformly |
| **the answer never reaches the squid** | the experiment never writes to brain state (instrumented dict); and two worlds stepped through an identical trial differing *only* in which cup holds the food produce **bit-identical brain state** |
| `can_see_food` keeps its meaning | 100 when the food is there to be seen, 0 when it is not, 0 when it is behind the squid — all via the shipping vision worker |
| no new neuron or sensor | the sensor block is exactly `DEFAULT_INPUT_SENSORS`; the source contains none of the forbidden names; any neuron that appears has a recorded birth from neurogenesis |
| baseline is 1/3 | ~180 pooled no-information trials |
| no fixed strategy beats chance | "always the left cup", "always cup B", all of them |
| omissions are unrelated to the answer | play rate per baited slot |
| **the scoring can detect real learning** | fed a squid that knows the answer, it says so |
| frozen evaluation is frozen | not one weight, ledger event or neuron changes |
| the control could not have learned | every synaptic write refused |
| differences correspond to real machinery | learning-arm trials carry the weight deltas and provenance events that happened during them; frozen-arm trials carry none |
| the game path is honest | cups and the ghost marker carry no `category`, so `extract_scene_objects` never hands them to the squid; hiding empties `food_items`; the reveal feeds through `Squid.eat` |
