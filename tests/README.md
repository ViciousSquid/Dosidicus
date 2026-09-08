# Testing Dosidicus

Run everything:

```
python -m pytest tests/ -q
```

No display is needed. If a Qt-backed test complains about a display, set
`QT_QPA_PLATFORM=offscreen`.

## What is where

| File | What it covers |
| --- | --- |
| `test_headless_training.py` | **Start here if you want to study the brain.** Blank-brain control condition, reproducibility, the transfer function, Hebbian convergence, training outcomes, save/load, trainer↔game parity. |
| `test_neural_pipeline.py` | The full pipeline in the running game: sensors → propagation → learning → behaviour, plus the innate reflexes and what has to be learned. |
| `test_organism.py` | Whole-life behavioural experiments — two squid raised differently, and whether the brain can explain the difference. |
| `test_transparency.py` | Whether the brain can account for itself: provenance of every weight and neuron. |
| `test_learning.py` | Plasticity rules in isolation. |
| `test_squid_statistics.py`, `test_statistics_*.py` | The lifetime statistics model, its persistence and its wiring to the UI. |

## Studying the brain

The brain is meant to be usable as an object of study, not only as a game.
Three things make a result checkable by someone else.

### 1. A control condition — the blank 8-neuron brain

```python
from headless_trainer import HeadlessBrain, TrainingConfig

brain = HeadlessBrain(TrainingConfig(blank=True))
# 8 neurons, 0 synapses, no innate reflexes
```

A blank brain has only the eight required neurons and nothing else, so
anything it knows at the end of a run was learned during that run. Contrast
the default, which hatches the newborn a real squid gets — able to move, eat
and flee from birth (see `src/brain_constants.INNATE_ACTION_WIRING`).

From the command line:

```
python headless/headless_trainer.py --blank --ticks 10000 --output trained.json
```

### 2. Reproducibility — seed the run

```
python headless/headless_trainer.py --blank --seed 42 --ticks 10000 --output a.json
python headless/headless_trainer.py --blank --seed 42 --ticks 10000 --output b.json
# a.json and b.json are identical apart from the export timestamp
```

Or in code:

```python
from headless_trainer import HeadlessSimulation, TrainingConfig

sim = HeadlessSimulation(TrainingConfig(seed=42, blank=True))
stats = sim.run(ticks=10000, progress_interval=0)
sim.brain.save_brain("trained.json")
```

Same seed, same brain, same tick count → the same trained brain. Without a
seed the run is still valid, just not reproducible.

### 3. Mechanisms that hold

`test_headless_training.py` checks the project's stated claims against the
running code rather than the documentation, among them:

- a silent sensor contributes nothing (a sensor rests at 0, a drive at 50);
- a saturated sensor pushes exactly as hard as a saturated drive;
- co-active neurons develop an excitatory synapse, anti-correlated ones an
  inhibitory synapse — weights are signed, and an avoidance IS a negative
  weight;
- propagation never writes a sensor or a core stat;
- neurogenesis stays inside its configured neuron ceiling;
- the trainer and the game step the network with the same function and hatch
  from the same innate tables, so a brain trained headlessly behaves the same
  way when a squid runs it.

If one of those fails, the mechanism it names has changed — that is the point
of stating them as tests.

## Writing a new experiment

```python
sim = HeadlessSimulation(TrainingConfig(seed=1, blank=True))
sim.load_scenario("stress_test")        # see TRAINING_SCENARIOS
sim.run(ticks=5000, progress_interval=0)

print(sim.brain.get_statistics())
print(sim.brain.explain_weight(("hunger", "anxiety")))   # why this weight?
```

Every weight and every grown neuron carries its provenance, so a finding can
be traced back to the experience that produced it rather than asserted.
