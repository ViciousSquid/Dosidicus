# Raw run logs

Each file is the unedited stdout of the command named below, run from the repo
root. Nothing here has been summarised or filtered.

| file | command | note |
|---|---|---|
| `replication-A-seeds-2-7-17-43-101.txt` | `python headless/cup_experiment_runner.py --seed-list 2,7,17,43,101 --naive 30 --train 50 --eval 50 --no-growth` | Re-run from the current commit so the published numbers match a command anyone can issue. |
| `replication-B-seeds-200-204.txt` | `python headless/cup_experiment_runner.py --seed 200 --seeds 5 --naive 30 --train 50 --eval 50 --no-growth` | A consecutive seed block, chosen after replication A specifically so it could not have been picked for its answer. |
| `exploratory-run-seeds-2-7-17-43-101.txt` | an ad-hoc driver calling `run_paired()` per seed | **Superseded.** The exploratory run that produced the near-miss false positive described in `../04-what-went-wrong.md`. Kept because it is the evidence for that account, not because its numbers are cited. It predates the `--seeds` CLI and prints no pooled statistics. |
| `test-suite-run.txt` | `python -m pytest tests/ -q` | 555 passed, 1 skipped, 613 subtests. |

## Reading a replication log

Four sections:

1. **per seed** — the eval-block comparison for each seed separately. Read this
   first; the spread is the point.
2. **pooled over every trial** — all seeds' trials combined, per arm, per block.
   The no-information (`naive`) row is the measured chance rate of the
   apparatus. The control arm's `train` row is worth attention: it can read
   "above chance" while having learned nothing.
3. **the verdict** — learning arm against frozen control, for both measures.
   This is the comparison the design turns on.
4. Per-seed reports also carry fixed-strategy scores, omission bias, the
   frozen-evaluation check, and the provenance ledger's mechanism totals.

## Reproducibility

Runs are seeded and deterministic: `CupWorld.__init__` seeds both its own
`random.Random` and the global `random` module, because
`decision_engine.select_action` draws its tie-breaking jitter from the latter.
Same seed, same settings, same commit → same numbers.

A run takes roughly twenty minutes; both arms of five seeds is about ten
paired runs of 130 trials each.
