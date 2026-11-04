# Newborn weight-space experiment

This branch directly changes three innate synaptic weights, runs a paired A/B neural-state test against the exact original 3.2.0 defaults, and retains detailed documentation, the reproduction commands and a CI workflow.

**Full experiment README:** [experiments/weight_space/README.md](experiments/weight_space/README.md).

To rerun: `python -m pytest -q tests/test_weight_space_experiment.py` then `python -m experiments.weight_space.experiment --json experiments/weight_space/results.json`.

This test measures action activation and threshold crossings. It **does not establish general intelligence, survival improvement or long-term learning gains**.
