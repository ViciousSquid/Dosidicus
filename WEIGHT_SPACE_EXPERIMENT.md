# Newborn weight-space experiment

This branch directly changes three innate synaptic weights, runs a paired A/B neural-state test against the exact original 3.2.0 defaults, and retains detailed documentation, the reproduction commands and a CI workflow.

**Full experiment README:** [experiments/weight_space/README.md](experiments/weight_space/README.md).

**Measured:** the predeclared neural-probe benchmark improved substantially, but a subsequent broader state sweep detected a **no-threat feeding regression**. This is therefore a documented experimental result, **not** a recommended release change. See [RESULTS.md](experiments/weight_space/RESULTS.md) and [GRID_RESULTS.md](experiments/weight_space/GRID_RESULTS.md).

**Final experiment finding:** [The action-coupled test and weight-only learning-transfer comparison](experiments/weight_space/CLOSED_LOOP_RESULTS.md) did **not** demonstrate a smarter squid. It documents the existing trainer's random food-reward flaw and a likely sensor-to-action latency bottleneck. The full [methodology](experiments/weight_space/CLOSED_LOOP.md), [static results](experiments/weight_space/RESULTS.md) and [out-of-sample sweep](experiments/weight_space/GRID_RESULTS.md) are preserved. Production is unchanged.

To rerun: `python -m pytest -q tests/test_weight_space_experiment.py` then `python -m experiments.weight_space.experiment --json experiments/weight_space/results.json`.

This test measures action activation and threshold crossings. It **does not establish general intelligence, survival improvement or long-term learning gains**.
