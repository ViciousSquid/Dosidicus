#### view source: _[decision_engine.py](https://github.com/ViciousSquid/Dosidicus/blob/2.6.1.2_LatestVersion/src/decision_engine.py)_ _version 2.6.1.2_

## Overview

```
 exploration of emergent behavioural complexity via dynamic, biologically-inspired neural architecture rather than a static state machine. 
```

The **Decision Engine** is the core action-selection system for Dosidicus. It is responsible for selecting and executing behaviour based on the squid’s *current neural state*, *physiological drives*, *memory influences*, and *personality modifiers*. 

Unlike traditional game AI systems (finite-state machines, behaviour trees, or rule stacks), the Decision Engine is **neural-first**: it does not directly reason about the world. Instead, *all perception and context must flow through the brain*.

In practical terms, this means behaviour is not scripted. It **emerges** from continuous internal signals competing for expression.

The engine is designed to be:

* Explainable (full decision traces are recorded)
* Extensible (new drives, memories, or actions integrate naturally)
* Compatible with future learning systems (dopamine, reinforcement, plasticity)

---

## Design Philosophy

### Neural-First Authority

The Decision Engine treats the brain as the **single source of truth**. It does not perform manual world queries (e.g. checking for food, scanning objects) to *decide* what to do. Instead, it consumes:

* Perceptual neuron outputs (via [`BrainNeuronHooks`](../source-reference/brain_neuron_hooks.py.md))
* Internal state neurons (hunger, anxiety, curiosity, etc.)
* Learned and persistent neural values

Direct world interaction is limited to *execution*, not *decision-making*.

### Continuous Competition

Actions are not triggered by rules. Instead, all candidate actions receive **weights** derived from internal signals. These weights compete, and the strongest wins. Small differences matter, enabling hesitation, oscillation, and personality-driven variance.

### Modulation, Not Commands

Memory and personality do not issue instructions. They *bias* behaviour by scaling weights. This ensures:

* Memories influence but do not dominate
* Personalities remain relevant in all contexts
* New behaviours automatically inherit modulation

---

## Decision Pipeline

The decision process is executed in six structured stages.

---

### 1. Perceptual & Brain State Construction

All perceptual input is retrieved via [`BrainNeuronHooks`](../source-reference/brain_neuron_hooks.py.md):

* Temporal sensors are decayed each tick
* No manual perception checks are allowed

The full brain state is constructed from:

* Core neurons
* Learned neurons
* Perceptual inputs (merged defensively)

This combined state represents the squid’s *entire subjective reality* at the moment of decision.

---

### 2. Memory Influence

Active memories are retrieved from the memory manager and converted into **multiplicative biases** on specific actions.

Examples:

* Positive food memories bias eating
* Object interaction memories bias play and throwing
* Startle memories suppress exploration and increase comfort-seeking

Memory effects are:

* Directional (positive or negative bias)
* Non-deterministic
* Stackable

This models habits, preferences, and learned aversions rather than explicit recall.

---

### 3. Physiological Urgency (Nonlinear Drives)

Physiological needs generate **exponential urgency curves**:

* Hunger amplifies eating
* Sleepiness amplifies sleeping

Nonlinear scaling ensures that high-need states *crowd out* other motivations rather than simply increasing priority linearly.

#### Reflex Overrides

Certain extreme states bypass competition entirely:

* Exhaustion → forced sleep
* Active sleep → no decision
* Extreme external stimulus → startle response

These represent **reflex arcs**, not cognitive decisions.

---

### 4. Base Action Weight Construction

Each candidate action receives a base weight derived from the brain state.

Actions include:

* Exploring
* Eating
* Approaching plants (comfort-seeking)
* Playing
* Throwing objects
* Sleeping
* Fleeing

Weights are influenced by:

* Drives (hunger, curiosity, satisfaction)
* Threat and anxiety
* Perceptual confidence (e.g. food visibility)
* Contextual suppressors (illness, external stimuli)

This stage defines *what the squid wants* before learning, memory, or personality intervene.

---

### 5. Memory & Personality Modulation

#### Memory Modifiers

Memory multipliers are applied to relevant actions, biasing selection without enforcing outcomes.

#### Personality Modifiers

[Personalities](../neural-network/Personality.md) act as **gain controls**:

* **Adventurous**: boosts exploration and play
* **Timid**: suppresses exploration, amplifies comfort-seeking
* **Greedy**: amplifies eating
* **Lazy**: suppresses energetic actions
* **Energetic**: boosts play and exploration

Personality does not define behaviour — it shapes *how strongly* drives express themselves.

#### Anxiety Coupling

High anxiety further amplifies comfort-seeking behaviour, creating feedback between affect and action selection.

---

### 6. Stochastic Selection & Confidence

After all modifiers:

* Small stochastic noise is applied to prevent determinism
* The highest-weighted action is selected

#### Confidence Metric

Decision confidence is computed as the relative margin between the top two competing actions.

This signal can be used for:

* Animation blending
* UI visualization
* Learning-rate modulation
* Behavioural hesitation

---

## Execution Phase

Once an action is selected, it is executed via `_execute_neural_decision`.

Key principles:

* Execution respects neural intent
* World scanning is minimized
* Fallback behaviours preserve personality flavour

Execution returns a *descriptive outcome string*, not just an action label, enabling rich UI feedback.

---

## Decision Tracing & Visualization

Each decision produces a full trace containing:

* Raw perceptual inputs
* Brain state snapshot
* Base action weights
* Memory influences
* Urgency multipliers
* Personality modifiers
* Final adjusted weights
* Selected action
* Confidence score

This trace is exposed to the Brain Tool UI for inspection and debugging.

---

## What the Decision Engine Is (and Is Not)

### It Is:

* A neural-modulated action selection system
* Continuous and explainable
* Designed for emergent behaviour
* Compatible with learning extensions

### It Is Not:

* A finite-state machine
* A behaviour tree
* A planner or lookahead system
* A reinforcement learner (yet)

---

## Future Extensions

The Decision Engine is intentionally structured to support:

* Dopaminergic reinforcement signals
* Action-value learning
* Noise modulation by arousal or confidence
* Fully neural affordance perception

The hardest architectural work — unified perception, continuous competition, and traceability — is already in place.

---

## Summary

The Decision Engine forms the behavioural core of Dosidicus. By enforcing neural authority, continuous competition, and modulation-based influence, it produces behaviour that is adaptive, interpretable, and personality-consistent — without relying on brittle scripts or hard-coded modes.

It is not merely a controller, but a foundation for a growing cognitive system.
