A headless training tool is included in the `headless` folder. This can be used to train brains in a time-accelerated environment 

* **Headless Operation**: No GUI required, runs purely on CPU
* **Accelerated Time**: thousands of ticks per second (vs ~1 tick/second in real-time)
* **The same engine as the game**: propagation, plasticity, spike timing, causal
  learning, sleep consolidation, capability diagnosis and neurogenesis are all
  imported from `src/`, so a brain trained here behaves identically when the
  squid runs it. None of those modules needs Qt.
* **Capability-driven neurogenesis**: new structure appears when the network
  persistently cannot represent, regulate or express something — the same
  question the game asks.
* **Provenance**: the trainer records why every weight moved and why every
  neuron exists, the same as the game does
  (`brain.explain_weight(...)`, `brain.explain_neuron(...)`).
* **Training Scenarios**: Predefined scenarios for different training goals
* **Export Trained Brains**: Save trained brains back to JSON for use in the main game
* **A blank control condition**: `--blank` hatches the eight required neurons
  with no synapses and no innate reflexes, so anything the brain knows at the
  end of a run was learned during it. Without the flag it hatches the newborn a
  real squid gets — able to move, eat and flee from birth.
* **Reproducible runs**: `--seed N` makes a run deterministic. The same seed,
  the same starting brain and the same tick count produce the same trained
  brain, so a result you publish is one somebody else can check.

### Running an experiment

```bash
# a blank brain, trained reproducibly
python headless/headless_trainer.py --blank --seed 42 --ticks 10000 -o trained.json

# the same command again produces an identical brain
python headless/headless_trainer.py --blank --seed 42 --ticks 10000 -o check.json
```

Or in Python:

```python
from headless_trainer import HeadlessSimulation, TrainingConfig

sim = HeadlessSimulation(TrainingConfig(seed=42, blank=True))
sim.run(ticks=10000, progress_interval=0)
sim.brain.save_brain("trained.json")

print(sim.brain.explain_weight(("hunger", "anxiety")))   # why this weight?
```

### The saved file can be asked *why*

A trained brain is written with its **whole account of itself** — the
provenance ledger, the causal record, the capability diagnosis, the plasticity
and consolidation state — under the same keys the game's save uses. Load one
back and it answers exactly what it answered before it was written out:

```
When Stress: Filth Avoidance is high, satisfaction strongly goes up.
  Learned from: ... watched together across 29 moments of the squid's life
  Why it changed: last strengthened by 0.116 because they kept happening
    together (measured correlation +1.00)
  Confidence: 83% (very confident), strength +0.78
```

Until v5.0 the export carried the network and nothing else, so a brain trained
here arrived with an evolved network and no idea why any of it was the way it
was. You could read its weights; you could not ask it anything.

### A note on time

One tick is one second of the squid's life. The trainer advances simulated
seconds with the ticks, and the neurogenesis engine reads that clock instead of
the wall clock, so `neurogenesis_cooldown` means what it says even when 1 500
ticks run per real second. Before v4.0 the trainer had its own propagation
(no neutral baseline, a 0.1 timestep, clamped to −100…100), its own Hebbian
rule (a non-negative product, so a trained brain could not contain a single
inhibitory synapse) and its own growth thresholds — a brain trained here was
simply not the same object the game ran.

Documentation for this tool can be found here: https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/headless/README_headless_trainer.md

#### Still experimental, but it now trains the same brain the game runs.


#### `headless_launcher.html` is a user-friendly launcher for this tool: drag and drop or Browse for a brain and then select how to train it and for how long

<img src="https://github.com/user-attachments/assets/3fdc4814-85ca-434f-a7c8-ef311131377b" width="800">