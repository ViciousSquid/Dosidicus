### version 3.1.3.0
`8 Sep 2026`

#### The Neuron Laboratory now explains, rather than displays

Double-clicking a neuron used to give you a raw weight table, a hypothetical
impact table and a static "did you know" tip. All three described the *category*
a neuron fell into rather than the neuron: a table of numbers is not an
explanation, a simulated impact is not something that happened, and a tip keyed
on a neuron's name says the same thing about every neuron that shares it. A
grown neuron with a perfectly good birth record in the ledger was told its
"purpose was inferred from birth context", because the tip consulted the ledger
only after it had already given up.

The Deep Inspector now answers six questions, in the order somebody actually
asks them:

* **What is this?** — what kind of neuron, and *who writes it each tick*: the
  world, the squid's body, the network, or what the squid is currently doing.
  What it reads right now in words rather than as a number. Whether it is part
  of a problem the brain has not solved.
* **Why does this neuron exist?** — the birth record, plus the measurements
  behind the diagnosis. A diagnosis without its evidence is an assertion.
* **What does it stand for?** — measured, not asserted. The capability monitor
  keeps, for every recurring situation and every action the squid performs, how
  the whole network behaves while it holds; the separation between this
  neuron's activation then and the rest of the time is Cohen's *d*. It is the
  same statistic the representation detector uses, read from the same totals,
  so what the Laboratory says a neuron means and what neurogenesis believes
  about it can never disagree. A neuron that stands for nothing is told so.
* **What do its connections mean?** — each synapse as a sentence, with the
  ledger's running total naming the mechanism responsible for its value.
* **What has it actually done?** — the recorded influence on the squid's
  physiology, not a simulation of what it could do. The projection is still
  there, at the end, labelled as one.
* **What has changed here, and why** — every recorded change, with its evidence.

The Live Overview's counter bars are gone. They filled toward novelty, stress
and reward thresholds that stopped deciding anything in v4.0. In their place is
the diagnosis growth actually consults: what the brain currently cannot do,
each deficit's severity, and whether it is ready to grow structure, still being
watched, or already shrinking under ordinary learning.

#### A silent sensor was not silent

The documentation has always said that activations run 0-100 with 50 as the
neutral baseline, "so a silent input contributes nothing". That was false for
every sense organ in the network. A sensor rests at **zero**, not at 50, so
`can_see_food` reading 0 - the squid cannot see any food - contributed
`-50 x weight`: as loud as seeing food, and pointing the other way.

A squid born with the instinct `can_see_food -> happiness +0.5` was therefore
made actively unhappy by the *absence* of food, every tick of its life, at
exactly the strength that its presence made it happy. Every association learned
with anything rare encoded the base rate rather than the contingency.

`propagation.signal_of()` is now the one place the project decides what an
activation means as a contribution, and everything that reads one goes through
it: propagation, neural modulation, the corrective-push measurement in the
capability monitor, the acute-deficit test in neurogenesis, the inspection
transfer function and the Laboratory's projection. A sensor at full signal
contributes exactly what it always did, so a brain behaves as before whenever
its senses have something to report. What has changed is what silence means:
nothing, which is what silence is.

Also: a neuron was reported as standing for a situation it helped define, which
is the neuron restating itself; and a neuron pinned at one value inside a
situation and another outside produced a Cohen's *d* in the dozens, which is
arithmetically correct and tells a reader nothing.

### version 3.1.2.0
`8 Sep 2026`

#### When the squid cannot tell which of its own actions did it

If wiggling and fluttering always happen together and satisfaction always
follows, Rescorla-Wagner settlement gives each of them half the credit. That is
the honest answer, and v3.1.1.0 left it there. Two permanent half-strength
claims are not knowledge, though, and no amount of repeating the same
experience improves them.

The causal ledger now records, for every ordered pair of the squid's
behaviours, how often the two ran together and how often the first ran
*without* the second. An outcome whose credit is split between behaviours that
have never once been observed apart is reported to the player as what it is —
an open question rather than two facts — and handed to the capability monitor,
which asks the structural half: does any neuron in this brain fire differently
for one of them than for the other?

When the answer is no, that is a **causal-differentiation deficit**, the sixth
kind, and the squid grows a neuron that stands for one of the behaviours and
nothing else. It is driven by the action rather than by synapses (a new
"externally driven" role, which propagation leaves alone exactly as it leaves a
sensor alone), and its single outgoing synapse onto the disputed outcome is
created **at zero**. It encodes neither the confounded pair nor a guess about
which one is the cause; it is somewhere for evidence to go. The first time one
of the behaviours happens without the other, ordinary plasticity and ordinary
settlement resolve it, and the pathway from the real cause is the one that
strengthens.

Neurogenesis cannot discover what the environment never showed the squid. It
can make sure that when the environment finally does show it, the brain has
somewhere to put the answer.

#### Ten defects the new test suite found

`tests/test_organism.py` runs the real BrainWidget inside a scripted world and
asserts on what the squid demonstrably did. Writing it turned up ten things
that were wrong, all fixed at source rather than tested around.

**Cue competition was still a race.** Only the episode that happened to expire
was updated against an outcome. Two behaviours that always overlap almost never
expire on the same tick, so the first to settle took the whole error and the
second learned nothing. Every action in scope is now updated on the shared
prediction error, which is both order-independent and what Rescorla and Wagner
actually say.

**Overlap was read from the wrong place.** Which behaviours counted as
concurrent was decided by what happened to be open at settlement time, so of
two behaviours that always overlap one looked like it always had company and
the other like it never did. It is now read from the episodes' own windows,
including recently settled ones.

**The background drift measured a background containing the thing being
tested.** The probe ran during action windows too, so an action's effect was
compared against an average that already included it. Fixing it by running the
probe only while idle almost never fired, because the squid is almost always
doing something. Every settled window is now filed against the actions running
in it and in a per-drive total, and the background is the difference.

**Spike timing had no clock of its own.** STDP measured spike intervals on the
wall clock, so a headless trainer stepping 1 500 ticks a real second presented
every spike as arriving under a millisecond after the last — inside any
plausible window — and computed a delta of exactly zero for every synapse. A
brain trained without the GUI had no spike timing in it at all. The plasticity
engine and the spike tracker now share a clock, as the capability monitor,
causal ledger and neurogenesis engine already did; the trainer sets all four to
simulated seconds and no longer has to disable the deficit age gate.

**Every squid was born with a different brain.** `initialize_weights()` built a
newborn out of 40% random connections at random weights in [-1, +1] — assigned
straight into the weights dict, so none of them could say where it came from —
while the headless trainer hatched from a fixed innate table, and two further
places in BrainWidget wrote `can_see_food` connections afterwards, one of them
behind a coin flip. The instincts of the species are now written once, in
`brain_constants.INNATE_CONNECTIONS`, through the recorded write path. "The
same squid, raised differently" is now a comparison anyone can make.

**The differentiation detector diagnosed healthy structure and then its own
remedy.** Two anti-correlated sources pushing a neuron in *opposite* directions
is push-pull — the shape of every regulator the engine grows — not an
overloaded neuron; only same-signed drivers can conflict. And because the
remedy hands one driver to a new neuron, that new neuron is necessarily still
anti-correlated with the one that stayed, so the monitor re-diagnosed the
conflict it had just resolved, one neuron further out, until it hit the type
cap. Both are fixed at the detector.

**Correlations were computed on constants.** Two drives wobbling by a tenth of
a point in opposite directions read as a perfect anti-correlation, and the brain
grew a neuron to separate them. A variance floor of two activation points now
applies.

**A cue could be its own outcome.** "Satisfaction predicts satisfaction" was
reported as an expression deficit, and the remedy wired satisfaction to a new
neuron and back — a positive feedback loop grown on purpose.

**A sensor reading zero was the most salient thing in the world.** Cue capture
scored sensors by distance from 50, so "no food anywhere" outranked everything,
and the squid grew structure to act on the absence of food. A sensor is now
salient when it is reporting something.

**Restoring a neuron on load wrote unrecorded synapses**, and a synapse could
be created pointing *into* an action representation, which the world overwrites
every tick — the same inert-by-construction bug as a synapse into a sensor.

**A green test run still exited 134.** A BrainWidget owns a render thread, and
leaving it running made Qt abort the process after unittest had already printed
OK, so any CI watching the exit code called a passing run a failure.

#### The organism test suite

Sixty-five tests in `tests/test_organism.py`, none of them a unit test. Each
runs the production BrainWidget in a scripted, deterministic world and asserts
on an observable consequence: perception reaching the network, activation
propagating one hop per tick, episodes opening and settling, delayed outcomes
finding eligible synapses, potentiation and depression on real weights, sleep
replaying the same weight store the squid wakes up in, pruning removing real
synapses, an evolved brain surviving save/load, learning changing what the
sight of food does to a squid, and every one of it explicable afterwards in
plain English.

Seven of them are scripted lives run twice with the causality reversed: food
that pays off and food that does not, and the whole confounded-actions
lifecycle — confounded phase, persistent deficit, growth, separation,
resolution — run once with each behaviour as the true cause, checking that the
resulting brains differ accordingly and that a behaviour which never produced
the outcome is never credited with it.

The last group is a regression sweep of the repository for competing
implementations of propagation, Hebbian learning, STDP, eligibility traces,
three-factor learning, causal learning, neurogenesis, pruning, sleep
consolidation, weight mutation and provenance — plus a runtime audit that
replaces the live weights dict with one that records the identity of every
writer and asserts nothing reaches it except the recorded write path.

### version 3.1.1.0
`8 Sep 2026`

#### Architecture validation

The v3.1.0.0 architecture was audited by measurement rather than by reading:
every write to `brain.weights` was instrumented and diffed against the ledger,
and each of the four learning mechanisms was traced end to end in a running
game. Eight defects were found and fixed at source.

**Provenance was not actually total.** Two live entry points wrote synapses
without recording them: the Plugins menu's neurogenesis action and Shift+N.
Both created ghost neurons — no `FunctionalNeuron`, so caps and pruning could
not see them, no birth record, and random symmetric synapses including some
pointing into sensors. `src/ui.py` also held a fifth (dead, and broken) copy of
the old event thresholds. All of it now goes through the one creation path.
Unrecorded deletions in `prune_weak_neurons`, `intelligent_pruning` and the
tutorial were routed through `remove_weight`.

**The write path itself existed twice**, in BrainWidget and in the headless
trainer, with test doubles implementing a third. It is now
`neural_provenance.RecordedSynapses`, inherited by all of them, so a double
cannot pass a test against a path production does not have.

**STDP was applying the wrong sign to the wrong direction.**
`compute_symmetric_stdp` returns the stronger of the two orderings — always the
causal, positive one — and that value was applied to whichever direction
`orient()` chose. LTD never reached a weight. The commit now asks for the
directed delta of the synapse it is updating.

**STDP could only see simultaneity.** Its 0.5 s window was shorter than the
game's ~1 s tick, so two neurons that fired one tick apart were out of window
entirely and how much learning happened depended on how fast the machine ran.
The window is now measured in samples of the cadence the tracker is actually
fed at.

**The three-factor rule was inert.** Eligibility was restricted to pairs that
both crossed the spike threshold inside the timing window; over 600 ticks of
ordinary life that produced ten spikes, essentially none coincident, so no
outcome ever reached a synapse. Eligibility is now participation — a low-pass
of pre × post activity, which is the textbook definition — and a reward is
consumed in proportion to the credit it takes instead of clearing every trace,
so the first outcome to land no longer robs every concurrent behaviour.

**Reward was a step, not a rate.** One outcome touching ninety synapses at a
fixed 0.08 was worth more than a hundred plasticity commits, and it flattened
everything experience had built. It is now scaled by the same learning rate the
correlational rule uses and shares a fixed budget among the synapses that
earned it, so broader eligibility no longer means stronger learning.

**Actions did not compete for credit.** Two overlapping behaviours each
recorded the full measured consequence, so an action that merely happened to be
running while another produced the result acquired an identical contingency —
the "things that co-occur must be related" mistake, moved up from neurons to
actions. Episodes are now settled together by shared prediction error: perfect
confounds split the effect, and the moment one dissociates the real cause
absorbs it. A null outcome now teaches too, so a coincidence once learned can
be unlearned. Valence is the **surprise**, not the raw change, so a fully
predicted outcome stops paying out.

**Neurogenesis mixed timescales and could grow inert neurons.** The regulation
deficit compared a 240-tick complaint against a single-moment reading of the
corrective synapses; it now asks whether the drive is coming back, with no
arbitrary threshold on push magnitude. A neuron whose specialisation had no
entry in the wiring table could be born with *zero* synapses and then be
"rescued" by the connectivity detector; the table is complete and birth has a
viability post-condition. Reciprocal links are damped by
`[Neurogenesis.NeuronProperties] reciprocal_strength`, which config.ini has
declared since 2.4 and nothing read — copying the forward weight made every
grown neuron half of a runaway loop.

#### Also fixed

* `[Neurogenesis.NeuronProperties]` never reached the engine at all.
* The Laboratory's "force neurogenesis" button now grows a real neuron.
* A synapse that changes sign starts its behavioural record again, so the
  Knowledge tab can no longer say "satisfaction goes up … it has spent 600
  ticks lowering satisfaction".
* High-frequency thousandth-of-a-point changes are accounted for exactly but
  no longer narrated one by one, so they stop burying the changes that matter.

199 tests pass, including one regression test per defect above and an
end-to-end test that raises two squids with the same brain and opposite lives,
checks they learn opposite signs for the same sensor, and checks the Laboratory
and the Knowledge tab can reconstruct the fact, the reason and every individual
weight change behind it.

-------------------------

### version 3.1.0.0
`8 Sep 2026`

#### Neurogenesis is now capability-driven

New neurons no longer appear because an event crossed a threshold. They appear
because the network has a **persistent functional deficiency it cannot fix with
the structure it already has** — something it cannot represent, regulate or
express — and ordinary learning has already had its chance at it. New module
`capability.py` diagnoses five kinds of deficit from the live network; the
diagnosis is visible in the new Knowledge tab as it happens.

#### The squid works out what its own actions cause

New module `causal_learning.py`. Every behaviour opens an episode; its
consequence is measured over the following seconds and compared against how the
drives drift when it is *not* doing that. The outcome is then broadcast back
along the spike-timing eligibility traces — temporal credit assignment — so a
consequence that lands seconds after the action still reaches the synapses that
produced it.

#### Full provenance, and a Knowledge tab to read it

New module `neural_provenance.py`. Every synaptic change and every grown neuron
records its cause, its evidence and the experience behind it, and it is all
saved with the squid. The new **Knowledge** tab, the Learning tab and the Neuron
Laboratory read that record — they no longer reconstruct an approximation of it.

* *"Why did this weight change from 0.31 to 0.47?"*
* *"Why does this neuron exist?"*
* *"What does the squid know about food?"*

#### One implementation of every neural mechanism

* Forward propagation extracted to `propagation.py`; the game, the neurogenesis
  engine and the headless trainer now step a network identically.
* The **STDP plugin** no longer monkey-patches `BrainWorker` or keeps its own
  learner — it is an inspector over the engine's. Spike timing itself is core.
* The **Sleep Replay plugin** no longer runs a second replay engine over the
  same brain — it is an inspector over `ConsolidationManager`.
* `HebbianLearning` is now the squid's innate reflexes, delegating every write
  to the one recorded path, instead of a second weight formula.
* The **headless trainer** imports the real engine instead of reimplementing
  it. It previously had its own propagation, its own Hebbian rule (which could
  not produce an inhibitory synapse at all) and its own growth thresholds.
* `NeurogenesisTriggerSystem` and the `ShowmanNeurogenesis` wrapper are gone;
  the wrapper was constructed and immediately discarded, so `showmanship` did
  nothing. It now works, as a naming choice made once at birth.

#### Fixed

* STDP contributed **nothing**: the core blended a tuple where it expected a
  float, the exception was swallowed, and the spike-timing term was zero for
  every pair on every cycle.
* Eligibility traces were laid on the 20-second commit cycle while the window
  was 2 seconds, so the three-factor rule could never fire. Traces are now laid
  as the spikes happen, with an 8-second window.
* A grown neuron's display name rendered as the literal `{type}: {spec}{suffix}`
  because the localisation fallback dropped its arguments.
* `strength_multiplier` had no ceiling; long runs produced multipliers in the
  hundreds, so one neuron saturated the whole network.
* Structural wiring could be silently collapsed onto its own reverse edge,
  destroying the inhibition a regulator neuron exists for.
* `[Neurogenesis] showmanship`, `max_neurons` and `pruning_enabled` never
  reached the engine that reads them.
* `learn_from_sickness()` was disabled entirely — every one of its connections
  starts at `is_sick`, which was on the exclusion list.
* The Laboratory's "force neurogenesis" button wrote a state key nothing read.

-------------------------

### version 2.6.1.2
`23 Feb 2026`

* Optional [hardware AI accelerator support via ONNX Runtime](../neural-network/AI-Accelerator-Support.md) - _Experimental, disabled by default_

* NEW: [brain_to_keras.py](https://github.com/ViciousSquid/Dosidicus/blob/2.6.1.2_LatestVersion/extras/brain_to_keras.py) (from the dev branch) in the `extras` folder - _attempts to convert a Dosidicus brain.json to Keras v3 (experimental)_

* Improved Brain Tool short-term and long-term memory tabs: **more varied and verbose memories**
* **Random Humboldt squid facts** can occasionally appear in status bar
* FIXED: BrainTool Hebbian timers weren't in sync [(20)](https://github.com/ViciousSquid/Dosidicus/issues/20)
* FIXED squid now properly goes to sleep when sleepiness=max

-------------------------


### version 2.6.1.1
`20 Feb 2026`

### Milestone 2
* Added `linux_setup.sh`
* Code optimisations & bug fixes

-------------------------

### version 2.6.1.0

`21 Jan 2026`

#### build 1219
* Translation files for 7 languages: _English_, _French_, _Spanish_, _German_, _Chinese_, _Japanese_, _Millennial_
* [Stable release for Windows](https://github.com/ViciousSquid/Dosidicus/releases/tag/v2.6.1.0)

`18 Dec 2025`

#### build 1218 **Milestone 2** Release 
* Integrated Designer into Brain Tool
* Added ability to create custom neurons
* NEW: [Headless brain trainer](https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/headless/README_headless_trainer.md) with accelerated time epochs
* NEW: Global preferences window
* Added an additional 4 custom brains
* French and Spanish Translations (_does not currently include Designer_)

-------------------

### version 2.6.0.3
`11 Dec 2025`

* Added FEED, CLEAN, MEDICINE buttons to UI
* Added 5 example [custom brains](https://github.com/ViciousSquid/Dosidicus/tree/2.6.0.2_latest_release/custom_brains)
* Neuron/font sizes and other UI elements now configurable via config.ini
* FIXED: missing `update_score` method in `StatisticsWindow`
* [Brain Designer](../brain-tool/Brain-Designer.md) can now import current running brain from Brain Tool
* NEW: Neuron output bindings can be used to create simple IF THEN behaviours for the squid

-------------------

### version 2.6.0.2
`8 Dec 2025`

* NEW: [Brain Designer](../brain-tool/Brain-Designer.md) - create your own custom squid brains!
* NEW: 5 custom brain templates that can be edited however you like [[dir](https://github.com/ViciousSquid/Dosidicus/tree/2.6.0.1_latest_release/custom_brains)]
* NEW: [Example squid](../getting-started/Example-Squids.md) **Miroslav**

-------------------

### version 2.5.0.0
`3 Dec 2025`

* New [Save Viewer](../extras/SaveViewer.md)
* Added 8 additional plant decorations & associated stats
* Brain Network tab now has buttons for Experience Buffer and Neuron Laboratory
* Fixed a bug where the brain state was not being restored properly from save
* Added [showman wrapper](../source-reference/neurogenesis_show.py.md) for Neurogenesis
* Code refactoring and removal of legacy cruft (pre version 2.4.X)
* Feature-complete stable code-base 

-------------------

### version 2.4.5.1 _patch_
`25 Nov 2025`

* [Engine](../engine/Engine-Overview.md) update - Neurogenesis and hebbian calculations now in own thread so UI remains responsive
* **New**: Improved [multiplayer](../engine/Multiplayer.md) plugin!!
* **New**: [Achievements](../extras/Achievements.md) (50 to collect)
* **New**: Full interactive tutorial when starting a new game
* Every squid is born with a `uuid` that stays with him his entire life
* Added [Neuron Laboratory](../brain-tool/Neuron-Laboratory.md) via the View menu or by double clicking any neuron



-------------------

### version 2.4.5.0
`15 Nov 2025`

* Improved [plugin manager](../engine/Plugin-System.md)
* Massively overhauled and [improved](../source-reference/neurogenesis_show.py.md) neurogenesis
* Track statistics such as squid age, distance travelled, total foods eaten, etc
* Improved load/save mechanism (backward compatible with v2.3 saves and earlier)
* Hebbian now trains on 2 active neuron pairs at once
* Redesigned Brain Tool [learning tab](../brain-tool/Learning-Tab.md)
* Global counters now respect game speed
* Arcade-style (High-Score) system
* Animations throughout the UI


-------------------

### version 2.4.4.1
`04 Sept 2025`

* Code cleanup and stability improvements
* WIP: Track statistics such as squid age, distance travelled, total foods eaten, etc
* ADDED: Small chance of squid creating an ink cloud when startled
* ADDED: Experimental [multiplayer](../engine/Multiplayer.md) plugin

-------------------

### version 2.4.3

Milestone 1

**Initial stable release**

### **AUTHOR GOT A TATTOO** to celebrate 1 year of this project!

<img src="https://github.com/user-attachments/assets/fe50e8d8-cb76-4b20-830a-ea6af28bb608" width="250">

  <a href="https://www.buymeacoffee.com/vicioussquid" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>