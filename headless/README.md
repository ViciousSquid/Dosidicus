## Headless Brain Trainer
A standalone training system for Dosidicus neural network brains that runs without GUI overhead, enabling fast accelerated training of custom brain architectures.


## Features

- **Headless Operation**: No GUI required, runs purely on CPU
- **Accelerated Time**: Advances simulated seconds without a graphical frame; speed depends on neural size, learning, neurogenesis and hardware.
- **Custom Brain Loading**: Load brain architectures from JSON files
- **Neurogenesis**: Automatic creation of new neurons based on stress/novelty/reward triggers
- **Hebbian Learning**: Continuous weight updates based on co-activation
- **Training Scenarios**: Predefined scenarios for different training goals
- **Export Trained Brains**: Save trained brains back to JSON for use in the main game

## Installation

The headless **brain computations require NumPy** and current project Python; they do not require Qt for the trainer itself. The verified experiment uses **Python 3.11**. From the repo root: `python -m pip install numpy`. Desktop/game tests that import the UI also require PyQt5 and associated dependencies.

```bash
# Make executable (optional)
chmod +x headless_trainer.py
```

## Neural decisions drive the simulated body (experimental branch)

The headless trainer no longer grants food randomly just because food exists. Each tick runs the real shared neural propagation and action selection, and the body responds to **the chosen neuron-driven behaviour**:

- `eating` seeks a visible food item and only consumes it once close enough; `food_eaten` counts **self-obtained** meals.
- `exploring` requires an active locomotion neuron and causes wandering. A blank eight-neuron control, with no motor neurons, cannot wander or feed by accident.
- `fleeing` can terminate an observed startle; failing to flee has a simulated health cost.
- `sleeping`/involuntary `exhausted` enter finite sleep; they no longer arise from an independently scripted sleep threshold.
- `manual_feedings` records external scenario interventions separately. Manual feeds, cleaning and state injection cancel pending **causal-credit windows** rather than allowing a preceding squid action to take credit for the external benefit.

Per-tick percepts and body events remain simplified; this is **not a high-fidelity simulation of the full game**. The same `HeadlessBrain` and `select_action` functions are used, but spatial geometry, predators and social learning are still approximated or absent.

For a frozen evaluation run that cannot write new learned weights:

```python
from headless.headless_trainer import HeadlessSimulation
from src.portable_brain import TrainingConfig

sim = HeadlessSimulation(TrainingConfig(
    seed=42, learning_enabled=False, neurogenesis_enabled=False
))
results = sim.run(ticks=300, progress_interval=0)
print(results["food_eaten"], results["actions_selected"])
```

For the controlled original-vs-experimental birth-weight, learned-vs-untrained, matched-seed study and full per-run JSON:

```bash
python -m experiments.weight_space.trainer_transfer \
  --json experiments/weight_space/trainer_transfer_results.json
```

Read [experimental protocol and negative/positive observations](../experiments/weight_space/REAL_TRAINER_RESULTS.md). These are neural behavioural outcomes, **not an IQ or transfer-score benchmark of general intelligence**.

## Quick Start

```bash
# Train with default brain for 10,000 ticks
python headless_trainer.py --ticks 10000 --output my_trained_brain.json

# Train a custom brain
python headless_trainer.py --brain my_custom_brain.json --ticks 20000 --output trained.json

# Use a predefined scenario
python headless_trainer.py --brain my_brain.json --scenario stress_test --output stress_trained.json

# List available scenarios
python headless_trainer.py --list-scenarios
```

## Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--brain FILE` | `-b` | Path to brain JSON file to load |
| `--output FILE` | `-o` | Path to save trained brain (auto-generated if not specified) |
| `--ticks N` | `-t` | Number of simulation ticks (default: 10000) |
| `--scenario NAME` | `-s` | Use a predefined training scenario |
| `--list-scenarios` | | List available training scenarios |
| `--progress N` | `-p` | Progress report interval (default: 500, 0=quiet) |
| `--quiet` | `-q` | Minimal output |
| `--learning-rate F` | | Override Hebbian learning rate |
| `--neurogenesis BOOL` | | Enable/disable neurogenesis |
| `--max-neurons N` | | Maximum neurons allowed |

## Training Scenarios

### `balanced`
Standard balanced training with normal event rates. Good for general-purpose brain development.

### `stress_test`
High anxiety/stress conditions to develop resilience neurons. Includes:
- Reduced food availability
- Increased startle events
- Scripted high-anxiety events

### `reward_rich`
Frequent positive outcomes to develop reward pathways. Includes:
- High food spawn rate
- Reduced negative events
- Scripted feeding events

### `novelty_exploration`
High curiosity environment with new objects. Good for developing exploration behaviors.

### `endurance`
Long-duration (50,000 ticks) training with varied conditions.

## Brain JSON Format

Brains are stored as JSON files with the following structure:

```json
{
  "metadata": {
    "name": "My Brain",
    "description": "Description of the brain"
  },
  "positions": {
    "hunger": {"x": 127, "y": 81, "is_custom": false},
    "custom_neuron": {"x": 450, "y": 250, "is_custom": true}
  },
  "weights": {
    "hunger,satisfaction": -0.3,
    "happiness,satisfaction": 0.4
  },
  "neuron_shapes": {
    "custom_neuron": "pentagon"
  },
  "output_bindings": []
}
```

### Core Neurons (cannot be removed)
- `hunger`, `happiness`, `cleanliness`, `sleepiness`
- `satisfaction`, `anxiety`, `curiosity`

### Input Sensors
- `can_see_food`, `plant_proximity`, `external_stimulus`
- `is_eating`, `is_sleeping`, `is_sick`, `is_fleeing`, `is_startled`, `pursuing_food`

### Custom Neurons
Any neuron not in the core/sensor lists is treated as a custom neuron and will participate in Hebbian learning with boosted rates.

## Example Workflow

### 1. Create a custom brain in the Brain Designer
Use the [Brain Designer](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer) to create your architecture, then export it as JSON.

### 2. Train the brain headlessly
```bash
# Quick training
python headless_trainer.py -b my_design.json -t 50000 -o trained_v1.json

# Or with a scenario
python headless_trainer.py -b my_design.json -s stress_test -o stress_trained.json
```

### 3. Load the trained brain back into Dosidicus
Use the "Load Brain" button in the [Network tab](https://github.com/ViciousSquid/Dosidicus/wiki/Network-Tab) to load your trained brain.

## Training Tips

1. **Start with balanced training** to establish baseline connections
2. **Use stress_test** if you want resilience neurons for anxiety handling
3. **Use reward_rich** if you want strong satisfaction/happiness pathways
4. **Long training (50k+ ticks)** allows more sophisticated weight patterns to develop
5. **Multiple training rounds** with different scenarios can create well-rounded brains

## Performance

On modern hardware, expect:
- ~25,000-35,000 ticks/second
- A 50,000 tick training session completes in ~2 seconds
- A 1,000,000 tick session completes in ~30 seconds


## Integration with Dosidicus-2

The trained brain JSON files are fully compatible with:
- Brain Designer (import/export)
- Main game's "Load Brain" feature
- Save game custom brain storage

## License

Part of Dosidicus-2 project. [GPL-2.0 license](https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/LICENSE)
