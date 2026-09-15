# 01 — Architectural audit

*Performed before any experiment code was written.*

The brief asked for a demonstration that the squid can learn to follow food
hidden under a cup, using the existing architecture, with an explicit
instruction: **if the existing sensory and positional information is not
sufficient to distinguish the three cup locations, report the architectural
limitation rather than quietly adding a sensor to solve it.**

So the first question was not "how do I build this?" but "is this learnable at
all?" This is what the audit found.

---

## What the world can tell the network

Every value the world writes into the brain passes through one function:
`BrainNeuronHooks.get_input_neuron_values()` (`src/brain_neuron_hooks.py`). It
walks `brain_widget.neuron_positions`, skips the seven core stats, and calls a
registered handler for every remaining neuron that has one. The handlers are
enumerated in `DEFAULT_INPUT_SENSORS`:

| sensor | what it carries |
|---|---|
| `can_see_food` | **binary** — is there any food in the vision cone at all |
| `plant_proximity` | scalar distance to the nearest plant |
| `threat_level` | scalar, derived from anxiety and startle |
| `external_stimulus` | scalar, decaying, from resizes and interactions |
| `pursuing_food`, `is_sick`, `is_fleeing`, `is_eating`, `is_sleeping`, `is_startled` | binary state flags |

**Every one of them is a scalar with no spatial content.** `can_see_food` is the
crucial case: it answers *whether* there is food, never *where*. Two cups'
worth of food at opposite ends of the tank produce the identical activation.

## What the network can do about it

Behaviour is read off action neurons (`brain_constants.ACTION_NEURONS`):

```
act_move  act_eat  act_flee  act_play  act_shelter  act_rest  act_ink  act_collapse
```

**None of them is directional.** There is `act_eat`; there is no `act_go_left`.
The motor bank encodes *what to do*, never *which way*.

## The one place position appears — and why it is inert

`TamagotchiLogic.update_simulation` does put the squid's position into the dict
it hands to `update_brain`:

```python
"position": (self.squid.squid_x, self.squid.squid_y),
```

This looks like a spatial channel and is not one. `propagation.activation_of`
coerces a stored neuron value to the 0–100 scale and returns `None` for anything
that is not a bool or a number:

```python
def activation_of(raw) -> Optional[float]:
    if isinstance(raw, bool):  return 100.0 if raw else 0.0
    if isinstance(raw, (int, float)):  return float(raw)
    return None
```

`propagate()` skips any source whose `activation_of` is `None`. A tuple is
therefore invisible to every synapse in the network. `position` is bookkeeping
that renderers and the statistics model read; it is not perception.

## How the squid actually reaches food

Worth stating, because it is easy to mistake for a spatial capability.

1. **The innate reflex** (`Squid.move_squid`) — `get_visible_food()` returns
   positions from the vision cache, and the squid steers at the nearest. This is
   hard-wired, it interrupts whatever the decision engine was deliberating
   about, and it **needs no brain at all**. It operates on food the squid can
   *see*.
2. **The decision engine** (`DecisionEngine._execute`) — when `act_eat` wins, it
   calls `_nearest_food()`, which reads `logic.food_items` directly and sets a
   movement drive at it.

Both are outside the network. The network's contribution is *whether* to seek
food, never *where* food is. Note (2) in particular: it would happily home in on
food the squid cannot see, which is why the experiment has to remove hidden food
from `food_items` and not merely from view — see the leak analysis in
[`02-method-and-controls.md`](02-method-and-controls.md).

---

## Finding

> **The existing sensory and positional information is NOT sufficient for the
> squid to distinguish the three cup locations.**
>
> There is no input that differs between the three cups, and no output that
> differs between going to one and going to another. "The food is under the left
> cup" is not a proposition this network can represent.

**Experience cannot teach a representation the architecture cannot form.** No
amount of training, reward or plasticity changes this; it is a statement about
the shape of the network's input and output spaces, not about its weights.

Adding the missing channel — a positional sense, a directed action — is exactly
what the brief forbade, and correctly so: it would have converted a fact about
the architecture into an artefact of the experiment.

## What this made possible

A negative result known in advance is not a dead end. It let the experiment be
designed as a **test of the prediction** rather than a search for a win:

1. **Cup choice became a falsifiable prediction.** "Accuracy stays at chance"
   was written down before the first trial. If the squid had beaten the frozen
   control, the audit would have been wrong and that would have been the
   finding. It did not.
2. **It identified where learning *could* show.** How hard `act_eat` is driven
   while the food is hidden **is** an activation on an existing neuron, reached
   through synapses the plasticity engine already moves. That became the second
   measure — and it is the one that came back positive.
3. **It set the standard of proof.** Because the headline was expected to be a
   null, the instrument had to be shown to work. Hence the sensitivity tests in
   `tests/test_cup_experiment.py`: fed a squid that *does* know the answer, the
   scoring says so. A null from a dead instrument means nothing.

## Corollary: what would make the task learnable

Stated so the limitation is actionable rather than just a complaint. The
architecture would need **both**:

- an input that differs by location — a directional food sense, place cells, or
  an egocentric bearing-to-target signal; **and**
- an output that differs by direction — directional action neurons, or an
  action whose target the network selects.

Either alone is insufficient. A network that can tell left from right but cannot
act differently on the two has learned nothing it can use; a network that can
turn left or right on demand but cannot tell which is correct has nothing to
condition on.

That is a substantial architectural change with consequences far beyond a cup
game, which is why this experiment reports the limitation instead of making it.
