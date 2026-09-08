# Testing & Reproducibility

Dosidicus is meant to be usable as an object of study, not only as a game. That
means a result you get from it should be one somebody else can check.

```bash
python -m pytest tests/ -q          # the whole suite, no display needed
```

`tests/README.md` in the repository is the working guide. This page is the
summary.

---

## Three things that make a result checkable

### 1. A control condition — the blank 8-neuron brain

```python
from headless_trainer import HeadlessBrain, TrainingConfig

brain = HeadlessBrain(TrainingConfig(blank=True))
# 8 neurons, 0 synapses, no innate reflexes
```

A blank brain has only the eight required neurons and nothing else, so anything
it knows at the end of a run **was learned during that run**. The default
hatches the newborn a real squid gets — able to move, eat and flee from birth.

From the command line: `python headless/headless_trainer.py --blank ...`

### 2. Reproducibility — seed the run

```bash
python headless/headless_trainer.py --blank --seed 42 --ticks 10000 -o a.json
python headless/headless_trainer.py --blank --seed 42 --ticks 10000 -o b.json
# identical, apart from the export timestamp
```

Same seed, same starting brain, same tick count → the same trained brain. The
seed is applied before the squid picks its personality, so the determinism
covers the very first draw. Without a seed a run is still valid, just not
reproducible.

### 3. Stated mechanisms that actually hold

`tests/test_headless_training.py` checks the project's claims against the
running code rather than against this documentation:

* a **silent sensor contributes nothing** — a sensor rests at 0, a drive at 50
* a **saturated sensor pushes exactly as hard as a saturated drive**
* **co-active neurons develop an excitatory synapse**, anti-correlated ones an
  inhibitory one — weights are signed, and an avoidance *is* a negative weight
* **propagation never writes a sensor or a core stat** — the world owns one and
  the squid model owns the other, and two writers on one neuron is the class of
  bug `src/propagation.py` exists to remove
* **neurogenesis stays inside its configured neuron ceiling**
* the **trainer and the game step the same network** from the same innate
  tables, so a brain trained headlessly behaves the same way when a squid runs
  it
* a **saved brain can be asked why** — it carries its own provenance, and
  nothing is forgotten by being written to a file

If one of those fails, the mechanism it names has changed. That is the point of
stating them as tests rather than as prose.

---

## Asking a trained brain what it knows

```python
sim = HeadlessSimulation(TrainingConfig(seed=42, blank=True))
sim.run(ticks=10000, progress_interval=0)
sim.brain.save_brain("studied.json")

brain = HeadlessBrain(TrainingConfig(blank=True))
brain.load_brain_file("studied.json")

for item in brain.ledger.knowledge(limit=10):
    print(item.describe())

print(brain.explain_neuron("novelty_role_separation"))
print(brain.capability.describe())          # what it still cannot do
```

Which produces things like:

```
When Stress: Filth Avoidance is high, satisfaction strongly goes up.
  Learned from: ... watched together across 29 moments of the squid's life
  Why it changed: last strengthened by 0.116 because they kept happening
    together (measured correlation +1.00)
  Confidence: 83% (very confident), strength +0.78
  Effect on behaviour: when Stress: Filth Avoidance is active this nudges
    satisfaction up, which feeds straight into what the squid decides next
```

Every weight and every grown neuron carries its provenance, so a finding can be
traced back to the experience that produced it rather than asserted.

---

## Where the tests live

| File | What it covers |
| --- | --- |
| `test_headless_training.py` | **start here for study**: blank brain, reproducibility, the transfer function, Hebbian convergence, save/load, trainer↔game parity, knowledge extraction |
| `test_neural_pipeline.py` | the full pipeline in the running game: sensors → propagation → learning → behaviour; innate reflexes; action competition; the decision timeline |
| `test_organism.py` | whole-life behavioural experiments — two squid raised differently, and whether the brain can explain the difference |
| `test_transparency.py` | whether the brain can account for itself |
| `test_learning.py` | plasticity rules in isolation |
| `test_squid_statistics.py`, `test_statistics_*.py` | the lifetime statistics model and its persistence |
