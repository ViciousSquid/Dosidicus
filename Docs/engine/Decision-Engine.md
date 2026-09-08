#### view source: _[decision_engine.py](../../src/decision_engine.py)_ &nbsp;·&nbsp; _version 5.0_

## Overview

```
 exploration of emergent behavioural complexity via dynamic, biologically-inspired
 neural architecture rather than a static state machine.
```

The **Decision Engine** does not decide anything.

That sounds like a joke, but it is the whole design. The network has one
**action neuron** per thing the squid can do. Forward propagation drives those
neurons like any other, they **inhibit one another**, and whichever survives
that competition is what the squid does. The engine reads the outcome and
carries it out.

---

## What changed in 5.0, and why

Version 4.0 computed behaviour from hand-written formulas:

```python
weights["eating"] = hunger * (3.0 if can_see_food > 80 else 0.3) \
                    * 1.6 ** (hunger / 25)
weights["approaching_plant"] = (anxiety / 40) * (3.0 if near_plant else 0.5) \
                               * (4.0 if personality is TIMID else 1.8)
```

...and a dozen more like them, followed by a memory-influence table and a
per-personality multiplier table.

Those numbers *were* the squid's behaviour policy. The network could rewire
itself completely — grow neurons, invert synapses, consolidate a lifetime of
experience — and the squid would still do exactly what that arithmetic said,
because **nothing the squid learned was ever consulted when it chose what to
do**. The Brain Tool showed you a network that was, behaviourally, decorative.

In 5.0 the arithmetic *is* the network. Every number behind a behaviour is a
synapse, and every synapse is something Hebbian learning, STDP, sleep
consolidation or neurogenesis can move.

---

## Action neurons

Defined in `brain_constants.ACTION_NEURONS`:

| Neuron | Behaviour | Innate? |
| --- | --- | --- |
| `act_move` | swim around | yes — tonic bias |
| `act_eat` | go to food and eat | yes — sensorimotor prior |
| `act_flee` | flee | yes — reflex pathway |
| `act_ink` | release an ink cloud | yes — reflex, *probabilistic* |
| `act_collapse` | collapse from exhaustion | yes — homeostatic drive |
| `act_play` | play with a rock or poop | **no — must be learned** |
| `act_shelter` | shelter by a plant | **no — must be learned** |
| `act_rest` | choose to rest | **no — must be learned** |

Each has a **firing threshold** (`ACTION_FIRING_THRESHOLDS`) — the activation
it must reach before the squid will act on it. That threshold is a property of
the neuron, in the same units as its activation, and it is the *same* number
the actuator binding fires on, so an urge can never be "chosen" at a level too
weak to reach the body.

Action neurons **rest at zero**, not at the 50 midpoint a drive rests at. If
they rested at 50, an action the squid had never learned would sit permanently
at the midpoint and compete with the ones it had — a newborn would be born
wanting to do everything equally. Locomotion is the one exception and rests at
the midpoint, because a squid that is not doing anything else is still
swimming, and a motionless squid never meets anything it could learn from.

---

## What a squid is born knowing

Moving, eating and fleeing — and nothing else. It is not a rule anywhere; it
is structure, in `brain_constants.INNATE_ACTION_WIRING`, of four kinds:

**Sensorimotor priors.** `can_see_food → act_eat (+0.85)`. Seeing food drives
the neuron that swims to food. This is the "automatically move towards food"
instinct, and it is one synapse. A saturated `can_see_food` gives 42.5, and
`act_eat` fires at 38, so seeing food is enough on its own.

**Reflex pathways.** `is_startled → act_flee (+1.00)`, sustained by
`threat_level (+0.55)`. Startle alone reaches the flight threshold: a squid
that has just been frightened should not need corroborating evidence to run.
`is_startled → act_ink (+0.80)` runs *in parallel* with flight rather than
against it.

**Homeostatic drives.** `hunger → act_eat (+0.40)` sharpens the food prior.
`sleepiness → act_collapse (+0.95)` drives an involuntary collapse at the very
top of the sleepiness range.

**Tonic bias.** `curiosity → act_move (+0.45)`, on top of locomotion's resting
level.

**Sleep gating.** `is_sleeping` inhibits every voluntary action neuron at
−0.90. This is why there is no `if asleep:` branch in the engine — a sleeping
squid's actions sit below their thresholds *because something in its brain is
holding them there*, which is what being asleep is.

All of it is written through the recorded synapse path with mechanism
`innate`, so a newborn brain explains itself in the Knowledge tab like any
other, and **ordinary learning can strengthen, weaken or invert any of it**.
An instinct is a starting point, not a law.

### What must be learned

`act_play`, `act_shelter` and `act_rest` have **no innate wiring at all**.
Those neurons sit at zero until something the squid experiences builds a path
to them. A squid that never meets a rock never learns to play with one.

`LEARNED_ACTIONS` states this explicitly rather than leaving it to be inferred
from an absence — and `find_orphan_neurons()` knows to leave them alone, so
the brain does not "rescue" a capability the squid is supposed to earn.

Note the deliberate split between `act_collapse` and `act_rest`: **collapsing**
when exhausted is homeostasis every squid is born with; **choosing to rest**
before exhaustion is something it has to learn.

---

## Competition

`action_competition_wiring()` generates mutual inhibition between the
competing actions (−0.22), plus inhibition onto locomotion (−0.30).

Locomotion is inhibited by every other action and inhibits none of them. That
asymmetry is what makes swimming the thing a squid does when nothing else is
worth doing, **without anything having to declare it a fallback**: any real
urge quietly suppresses idling, and when the urge passes, idling comes back on
its own.

Reflexes sit outside the competition. Inking runs alongside flight rather than
against it — if it were ranked against fleeing it would sometimes win, and a
frightened squid would stand still and release a cloud of ink instead of
escaping. An imminent collapse silences everything.

The competition **settles rather than rings**: zero oscillation across every
scenario after 40 ticks, checked as a test
(`test_the_competition_settles_instead_of_oscillating`).

---

## Personality

Personality used to be a multiplier table applied to finished behaviour
weights, which put it outside the network entirely: nothing the squid
experienced could ever change it, and it appeared nowhere in the brain the
player was looking at.

A timid squid is now one **born with a stronger startle reflex**
(`INNATE_PERSONALITY_BIAS`, applied once when the squid's personality becomes
known). Ordinary learning can wear that down, so a timid squid that is never
frightened can genuinely grow out of it.

---

## The decision, in full

1. **Perception.** Every input reaches the brain through `BrainNeuronHooks`.
   There is no manual scanning of the scene.
2. **Read the action neurons.** Their activations *are* the behaviour weights.
3. **Rank by margin over each neuron's own threshold**, as a fraction of the
   room it had left. Comparing raw activations would be unfair between actions
   whose thresholds differ — a 50 is a strong wish to flee and a weak wish to
   eat. Reflexes and the fallback sit out.
4. **A little noise** (±6%), so a squid whose two strongest urges are neck and
   neck does not lock onto one of them forever. This is the only number in the
   file that is not a synapse.
5. **Carry it out** as a `DRIVE_DECISION` drive. `move_squid()` is the only
   thing that moves the squid, so routing through the drive keeps one movement
   channel and lets an output binding's urge outrank a decision.

If nothing clears a threshold, the squid swims — provided locomotion itself
clears *its* threshold. That is how a sleeping squid ends up doing nothing at
all rather than drifting around the tank in its sleep.

---

## Reflex probability

`INNATE_ACTION_BINDINGS` carries a **probability** per reflex. The ink cloud is
`0.35`: once `act_ink` crosses its threshold, the squid inks about a third of
the time. The cooldown is consumed on a failed roll too, so "a chance of
inking when startled" does not degrade into "keep rolling every tick until it
inks", which is the same as always inking, just later.

Keeping the chance on the binding makes it a visible, tunable property of the
reflex rather than a `random.random()` buried in a behaviour rule.

---

## Tracing

Every decision is kept — the last 240 of them — as a plain, serialisable
snapshot (`DecisionEngine.get_history()`), containing:

* the activation and threshold of **every** action neuron
* what each incoming synapse contributed to each action, this tick
* how hard each action was being pushed down by its rivals
* the margin each competitor had over its own threshold
* the sensors and drives that produced it

`DecisionEngine.explain(snapshot)` turns one into plain English:

> It chose to go and eat because that neuron reached 49, past the 38 it has to
> clear before the squid will act on it.
> What drove it: can see food (+42), hunger (+14).
> Nothing else was in contention; the closest was play, which reached 0 of the
> 38 it needed.
> Winning it also pushed the alternatives down: swim around (−7), flee (−5).

Every sentence is read off the snapshot. There is no claim in it the network
did not make. The [Decisions tab](../brain-tool/Decisions-Tab.md) renders this,
with a slider to scrub back through the history.

---

## What it is, and is not

**It is:** a reader of neural competition; continuous; explainable; entirely
subject to the learning mechanisms, because it has no policy of its own.

**It is not:** a finite-state machine; a behaviour tree; a planner; a
reinforcement learner (yet); and — as of 5.0 — no longer a table of formulas
wearing a neural network as a hat.

---

## Tests

`tests/test_neural_pipeline.py` holds the contract:

* `InnateBehaviourTests` — what a squid is born with, and what it is not
* `ActionCompetitionTests` — that actions genuinely inhibit one another, that
  danger beats appetite, that the competition settles
* `InnatePathwayShapeTests` — that no stimulus→action rule has crept back into
  `make_decision`
* `DecisionTimelineTests` — that every decision is kept, is plain data, and
  can explain itself
