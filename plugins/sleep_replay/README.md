# 🌙 Sleep Replay & Consolidation

Makes the squid's sleep cognitively meaningful. Instead of only restoring stats,
sleep now **consolidates the day's experience** and **renormalises the network**.

## What it does

| Phase | Behaviour | Biological analogue |
|-------|-----------|---------------------|
| **Awake** | Records which neurons fire together into a recency-weighted "experience buffer", biased by the memories the squid forms. | Hippocampal experience encoding |
| **Sleep onset** | Selects the strongest co-activations of the day and **replays** them in a series of bursts, strengthening (or creating) their connections. | Sharp-wave-ripple replay / systems consolidation |
| **Sleep** | **Prunes** weak, unused synapses and (optionally) gently down-scales the rest. | Synaptic homeostasis ("sleep prunes") |
| **Wake** | Fades the buffer so a new day begins, keeping a little momentum. | — |

Watch the **Learning tab** during sleep: replayed pairs appear as strengthened
(↗) connection cards, the network view animates the reinforced links, and the
console prints each ripple burst and the pruning summary.

## Design

- **Purely additive** – no core files are modified. Weights are mutated on the
  main thread (the same pattern the STDP plugin uses), so it's thread-safe.
- **Robust sleep detection** – polls `squid.is_sleeping` for edges, so it works
  for every sleep path, including forced sleep at 100% sleepiness (which fires
  no hook).
- **Respects existing safeguards** – connector neurons, pure-input sensors and
  immature neurons are never pruned, and the core `pruning_enabled` switch is
  honoured. Connections replayed during a sleep are always spared from pruning.
- **Qt-free core** – all the logic lives in `replay_core.py` and is unit-testable
  without the game running.

## Controls

Enabled by default. Open **Plugins → Sleep Replay**:

- **Control Panel…** – live buffer/replay/prune stats and runtime tuning.
- **Replay Now** – trigger a consolidation pass on demand (great for demos; works
  even while the squid is awake).
- **Enabled** – toggle the plugin.

## Key parameters (`ReplayConfig`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `coactivation_threshold` | 55.0 | Both neurons must exceed this to count as co-active. |
| `trace_decay` | 0.985 | How quickly older co-activations fade (the "day"). |
| `replay_top_k` | 8 | How many experiences are replayed per sleep. |
| `replay_cycles` | 5 | Number of ripple bursts across the sleep. |
| `replay_strength` | 0.05 | Base weight increment per fully-salient pair per cycle. |
| `prune_threshold` | 0.06 | Connections with `|weight|` below this are prunable. |
| `prune_min_age_sec` | 240 | Spare connections whose endpoints are younger than this. |
| `synaptic_downscale` | 0.0 | Optional global down-scaling of non-replayed weights (off by default). |

## Files

- `replay_core.py` — `ReplayConfig`, `CoactivationTracker`, `SleepReplayEngine` (Qt-free).
- `main.py` — `SleepReplayPlugin`: lifecycle, timers, sleep state machine, weight application, UI.
- `replay_control_panel.py` — runtime control panel.
