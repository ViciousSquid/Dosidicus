# Experiment findings

A lab notebook for controlled experiments on the Dosidicus brain. One
experiment so far.

Everything in here is a **record of what was actually measured**, including the
parts that did not work and one result that was very nearly reported wrongly.
`docs/` describes how to *use* a feature; this folder describes what was
*found*, what would falsify it, and how to reproduce it.

---

## Experiment 1 — Cup and food

> **Can an unchanged Dosidicus brain learn to follow food it can no longer see?**

A three-cup shell game. Bait a cup where the squid can see it, shuffle, hide the
food, let the squid pick. Known chance rate of 1/3, so the question gets a number
instead of an impression. No neurons and no sensors were added for it.

### The headline

Two measures, two different answers.

| measure | result | evidence |
|---|---|---|
| **Which cup does it go to?** | **No learning.** | **−1.1 pp** against the frozen control over 10 seeds and 720 scored trials, p = 0.76. Never significant in any individual seed, and the two replications disagree on the sign. |
| **Does it still want to eat once the food is hidden?** | **Real learning.** | **+7 pp** and **+19 pp** in the two replications, both p < 0.001, measured with plasticity frozen. |

**The squid does not learn *where* the food went. It does learn to go on
wanting it once it is gone.**

The first result was **predicted in advance** from a reading of the code, not
discovered by trying and failing — see the audit. The second runs entirely on
synapses the existing plasticity engine already moves, and is recorded in the
existing provenance ledger.

### The documents

| file | what it covers |
|---|---|
| [`01-architectural-audit.md`](01-architectural-audit.md) | The capability analysis done **before** anything was built, and why it made one of the two results a prediction rather than a finding. |
| [`02-method-and-controls.md`](02-method-and-controls.md) | The protocol, the apparatus, and every control — with the reasoning for each. |
| [`03-results.md`](03-results.md) | All the numbers: per-seed, pooled, both measures, both replications. |
| [`04-what-went-wrong.md`](04-what-went-wrong.md) | Five artefacts that produced convincing wrong answers before being caught, including one false positive that was nearly written up. |
| [`05-limitations.md`](05-limitations.md) | What this does **not** show, and what would change the conclusion. |
| [`data/`](data/) | Raw run logs, with the command that produced each. |

### Reproducing it

```bash
python headless/cup_experiment_runner.py --seed-list 2,7,17,43,101 --naive 30 --train 50 --eval 50 --no-growth
python headless/cup_experiment_runner.py --seed 200 --seeds 5 --naive 30 --train 50 --eval 50 --no-growth
```

Each takes on the order of twenty minutes. The implementation and the
user-facing description live in [`docs/cup_experiment.md`](../docs/cup_experiment.md).

### Status

Experimental. The null result on cup choice is solid and mechanistically
explained. The positive result on drive is statistically strong when pooled but
varies a lot seed to seed — see [`05-limitations.md`](05-limitations.md) before
citing it.
