#!/usr/bin/env python3
"""
Dosidicus-2 Headless Brain Trainer

Allows training custom neural network brains without GUI overhead.
Supports accelerated time, custom brain loading, and state persistence.

Usage:
    python headless_trainer.py --brain custom_brain.json --ticks 10000 --output trained_brain.json
    python headless_trainer.py --brain custom_brain.json --duration 3600 --speed 100
    python headless_trainer.py --list-scenarios
    python headless_trainer.py --brain my_brain.json --scenario stress_test

Author: Headless training system for Dosidicus-2
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from heapq import nlargest

# ============================================================================
# THE REAL ENGINE
#
# The trainer used to carry its own copies of everything: its own neuron
# categories, its own propagation (src_val * weight * 0.1, no neutral baseline,
# clamped to -100..100), its own Hebbian rule (a non-negative product, so it
# could never learn an aversion) and its own neurogenesis thresholds. A brain
# trained here therefore did not behave the same way when the squid ran it,
# which makes headless training worse than useless.
#
# It now imports the same modules the game does. None of them need Qt.
# ============================================================================
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.brain_constants import (  # noqa: E402
    CORE_STAT_NEURONS as CORE_NEURONS,
    PURE_INPUT_NEURONS as PURE_INPUTS,
    INPUT_SENSORS as _INPUT_SENSOR_POSITIONS,
    INNATE_CONNECTIONS,
    INNATE_ACTION_WIRING,
    action_competition_wiring,
    ACTION_NEURONS,
    newborn_neurons,
    action_resting_level,
    is_network_driven,
)
from src.propagation import ExternallyDriven, propagate  # noqa: E402
from src.plasticity import PlasticityEngine, PlasticityConfig  # noqa: E402
from src.capability import CapabilityMonitor  # noqa: E402
from src.causal_learning import ActionOutcomeLedger  # noqa: E402
from src.neural_provenance import CausalLedger, RecordedSynapses  # noqa: E402
from src.consolidation import ConsolidationManager  # noqa: E402
from src.neurogenesis import EnhancedNeurogenesis  # noqa: E402
from src.learning import LearningConfig  # noqa: E402
from src.portable_brain import HeadlessBrain, TrainingConfig  # noqa: E402
from src.decision_engine import select_action  # noqa: E402
from src.brain_constants import ACTION_THRESHOLDS  # noqa: E402
from src.predictive_cognition import PredictiveCortex  # noqa: E402

INPUT_SENSORS = set(_INPUT_SENSOR_POSITIONS) | {"can_see_food"}


class Personality(Enum):
    """Squid personality types"""
    TIMID = "timid"
    ADVENTUROUS = "adventurous"
    GREEDY = "greedy"
    STUBBORN = "stubborn"
    ENERGETIC = "energetic"


# ============================================================================
# CONFIGURATION
# ============================================================================



@dataclass
class TrainingScenario:
    """Predefined training scenarios"""
    name: str
    description: str
    duration_ticks: int
    config_overrides: Dict = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)


TRAINING_SCENARIOS = {
    "balanced": TrainingScenario(
        name="Balanced Training",
        description="Standard balanced training with normal event rates",
        duration_ticks=10000,
        config_overrides={},
        events=[]
    ),
    "stress_test": TrainingScenario(
        name="Stress Test",
        description="High anxiety/stress conditions to develop resilience neurons",
        duration_ticks=5000,
        config_overrides={
            "startle_chance": 0.02,
            "food_spawn_chance": 0.005,
        },
        events=[
            {"tick": 100, "type": "set_state", "state": {"anxiety": 80}},
            {"tick": 500, "type": "startle"},
            {"tick": 1000, "type": "set_state", "state": {"hunger": 90}},
        ]
    ),
    "reward_rich": TrainingScenario(
        name="Reward-Rich Environment",
        description="Frequent positive outcomes to develop reward pathways",
        duration_ticks=8000,
        config_overrides={
            "food_spawn_chance": 0.08,
            "poop_spawn_chance": 0.001,
        },
        events=[
            {"tick": 200, "type": "feed"},
            {"tick": 600, "type": "feed"},
            {"tick": 1200, "type": "feed"},
        ]
    ),
    "novelty_exploration": TrainingScenario(
        name="Novelty Exploration",
        description="High curiosity environment with new objects",
        duration_ticks=6000,
        config_overrides={
            "startle_chance": 0.001,
        },
        events=[
            {"tick": 100, "type": "set_state", "state": {"curiosity": 85}},
            {"tick": 300, "type": "new_object"},
            {"tick": 800, "type": "new_object"},
            {"tick": 1500, "type": "new_object"},
        ]
    ),
    "endurance": TrainingScenario(
        name="Endurance Training",
        description="Long-duration training with varied conditions",
        duration_ticks=50000,
        config_overrides={},
        events=[]
    ),
}


# ============================================================================
# HEADLESS SQUID (minimal state tracking)
# ============================================================================

class HeadlessSquid:
    """Minimal squid implementation for headless training"""
    
    def __init__(self, personality: Personality = None):
        self.personality = personality or random.choice(list(Personality))
        
        # Core stats (0-100)
        self.hunger = 50.0
        self.happiness = 50.0
        self.cleanliness = 80.0
        self.sleepiness = 20.0
        self.health = 100.0
        
        # Goal neurons
        self.satisfaction = 50.0
        self.anxiety = 10.0
        self.curiosity = 55.0
        
        # Boolean states
        self.is_sick = False
        self.is_sleeping = False
        self.is_eating = False
        self.is_fleeing = False
        self.is_startled = False
        self.pursuing_food = False
        self.sleep_ticks = 0
        
        # Position (normalized 0-1)
        self.x = 0.5
        self.y = 0.5
        self.direction = "right"
        
        # Status
        self.status = "roaming"
        
        # Tracking
        self.food_visible = False
        self.plant_nearby = False
        self.time_since_ate = 0
        self.time_since_slept = 0
        
    def get_state_dict(self) -> Dict[str, Any]:
        """Get current state as dictionary for brain updates"""
        return {
            "hunger": self.hunger,
            "happiness": self.happiness,
            "cleanliness": self.cleanliness,
            "sleepiness": self.sleepiness,
            "satisfaction": self.satisfaction,
            "anxiety": self.anxiety,
            "curiosity": self.curiosity,
            "is_sick": self.is_sick,
            "is_sleeping": self.is_sleeping,
            "is_eating": self.is_eating,
            "pursuing_food": self.pursuing_food,
            "is_fleeing": self.is_fleeing,
            "is_startled": self.is_startled,
            "threat_level": 100.0 if self.is_startled else 0.0,
            "can_see_food": 100.0 if self.food_visible else 0.0,
            "plant_proximity": 100.0 if self.plant_nearby else 0.0,
            "external_stimulus": 0.0,
            "direction": self.direction,
            "position": (self.x, self.y),
            "personality": self.personality.value,
            "status": self.status,
        }
    
    def update(self, dt: float = 1.0):
        """Update squid state for one tick"""
        # Natural stat changes
        self.hunger = min(100, self.hunger + 0.1 * dt)
        self.sleepiness = min(100, self.sleepiness + 0.05 * dt)
        self.cleanliness = max(0, self.cleanliness - 0.02 * dt)
        
        # Update time trackers
        self.time_since_ate += dt
        if not self.is_sleeping:
            self.time_since_slept += dt
        
        # Personality effects
        if self.personality == Personality.GREEDY:
            self.hunger = min(100, self.hunger + 0.05 * dt)
        elif self.personality == Personality.ENERGETIC:
            self.sleepiness = max(0, self.sleepiness - 0.02 * dt)
        elif self.personality == Personality.TIMID:
            if self.plant_nearby:
                self.anxiety = max(0, self.anxiety - 0.1 * dt)
        
        # Anxiety from needs
        if self.hunger > 70:
            self.anxiety = min(100, self.anxiety + 0.1 * dt)
        if self.cleanliness < 30:
            self.anxiety = min(100, self.anxiety + 0.05 * dt)
            
        # Satisfaction from good states
        if self.hunger < 30 and self.cleanliness > 70:
            self.satisfaction = min(100, self.satisfaction + 0.1 * dt)
        else:
            self.satisfaction = max(0, self.satisfaction - 0.02 * dt)
            
        # Happiness dynamics
        if self.anxiety > 50:
            self.happiness = max(0, self.happiness - 0.1 * dt)
        elif self.satisfaction > 60:
            self.happiness = min(100, self.happiness + 0.05 * dt)
            
        # Curiosity wanders
        self.curiosity += random.uniform(-0.5, 0.5) * dt
        self.curiosity = max(0, min(100, self.curiosity))
        
        # The world does not invent eating, fleeing or movement. These flags
        # describe the action chosen by the brain in this simulation tick.
        self.is_eating = False
        self.is_fleeing = False
        self.pursuing_food = False
        if self.is_startled and random.random() < 0.1:
            self.is_startled = False

        # Sleep was entered through act_rest / act_collapse, not a hidden
        # sleepiness threshold. A sleeping body recovers across ticks.
        if self.is_sleeping:
            self.sleepiness = max(0.0, self.sleepiness - 4.0 * dt)
            self.sleep_ticks -= 1
            if self.sleep_ticks <= 0 or self.sleepiness < 20:
                self.is_sleeping = False
                self.time_since_slept = 0
                self.status = "roaming"

        # Position changes only when the neural action bank drives movement.
            
    def feed(self):
        """Feed the squid"""
        self.hunger = max(0, self.hunger - 30)
        self.happiness = min(100, self.happiness + 10)
        self.satisfaction = min(100, self.satisfaction + 15)
        self.is_eating = True
        self.time_since_ate = 0
        self.status = "eating"
        
    def startle(self):
        """Startle the squid"""
        self.is_startled = True
        self.anxiety = min(100, self.anxiety + 20)
        self.happiness = max(0, self.happiness - 10)
        self.status = "startled"
        
    def clean(self):
        """Clean the environment"""
        self.cleanliness = min(100, self.cleanliness + 40)
        self.anxiety = max(0, self.anxiety - 5)


# ============================================================================
# HEADLESS BRAIN
# ============================================================================



# ============================================================================
# HEADLESS SIMULATION
# ============================================================================

class HeadlessSimulation:
    """
    Headless simulation runner for brain training.
    Runs the simulation loop without GUI, with accelerated time.
    """
    
    def __init__(self, config: TrainingConfig = None):
        self.config = config or TrainingConfig()
        # Seed BEFORE anything random happens - HeadlessSquid picks its
        # personality in its constructor - so a seeded run is reproducible from
        # the very first draw.
        if self.config.seed is not None:
            random.seed(self.config.seed)
        self.brain = HeadlessBrain(self.config)
        self.squid = HeadlessSquid()

        # Optional predictive-cognition research module (branch
        # research/transformer-predictive-cognition). Constructed after
        # the brain so it can register its prediction sensors through the
        # standard sensor interface. With predictive_mode='off' (the
        # default) it enables nothing, registers nothing and runs
        # nothing, and the engine behaves byte-identically to baseline.
        self.predictive = PredictiveCortex(self.brain, self.config)
        
        # Simulation state
        self.tick = 0
        self.running = False
        
        # Environment
        self.food_items: List[Dict] = []
        self.poop_items: List[Dict] = []
        
        # Statistics
        self.stats = {
            'ticks_completed': 0,
            'neurons_created': 0,
            'hebbian_updates': 0,
            'food_eaten': 0,        # ONLY food obtained through a neural action
            'manual_feedings': 0,   # scenario injection; not a learned success
            'food_approaches': 0,
            'food_seen_ticks': 0,
            'flee_actions': 0,
            'escaped_startles': 0,
            'unavoided_startle_ticks': 0,
            'actions_selected': {},
            'startles': 0,
            'peak_anxiety': 0,
            'peak_happiness': 0,
        }
        
        # Event queue (for scenarios)
        self.event_queue: List[Dict] = []
        
        # Progress callback
        self.progress_callback = None
        
    def load_brain(self, filepath: str) -> bool:
        """Load a brain from file"""
        return self.brain.load_brain_file(filepath)
        
    def load_scenario(self, scenario_name: str) -> bool:
        """Load a predefined training scenario"""
        if scenario_name not in TRAINING_SCENARIOS:
            print(f"✗ Unknown scenario: {scenario_name}")
            print(f"  Available: {list(TRAINING_SCENARIOS.keys())}")
            return False
            
        scenario = TRAINING_SCENARIOS[scenario_name]
        print(f"✓ Loading scenario: {scenario.name}")
        print(f"  Description: {scenario.description}")
        print(f"  Duration: {scenario.duration_ticks} ticks")
        
        # Apply config overrides
        for key, value in scenario.config_overrides.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                
        # Queue events
        self.event_queue = list(scenario.events)
        
        return True
        
    def run(self, ticks: int = 1000, progress_interval: int = 100) -> Dict:
        """
        Run the simulation for specified number of ticks.
        
        Args:
            ticks: Number of simulation ticks to run
            progress_interval: How often to report progress
            
        Returns:
            Dictionary with final statistics
        """
        self.running = True
        start_time = time.time()
        
        print(f"\n🚀 Starting headless training: {ticks} ticks")
        print(f"   Brain: {len(self.brain.positions)} neurons, {len(self.brain.weights)} connections")
        print()
        
        for self.tick in range(ticks):
            if not self.running:
                break
                
            # Process queued events
            self._process_events()
            
            # Simulation step
            self._simulation_step()
            
            # Progress report
            if progress_interval > 0 and (self.tick + 1) % progress_interval == 0:
                elapsed = time.time() - start_time
                tps = (self.tick + 1) / elapsed if elapsed > 0 else 0
                self._report_progress(tps)
                
        # Final statistics
        elapsed = time.time() - start_time
        self.stats['ticks_completed'] = self.tick + 1
        self.stats['elapsed_seconds'] = elapsed
        self.stats['ticks_per_second'] = (self.tick + 1) / elapsed if elapsed > 0 else 0
        self.stats['predictive'] = self.predictive.get_stats()
        
        print(f"\n✓ Training complete!")
        print(f"  Ticks: {self.stats['ticks_completed']}")
        print(f"  Time: {elapsed:.2f}s ({self.stats['ticks_per_second']:.1f} ticks/sec)")
        print(f"  Neurons created: {self.stats['neurons_created']}")
        print(f"  Hebbian updates: {self.stats['hebbian_updates']}")
        p = self.stats.get('predictive') or {}
        if p.get('enabled'):
            print(f"  Predictive cortex ({p.get('mode')}): "
                  f"train_steps={p.get('train_steps', 0)}, "
                  f"loss_ema={p.get('loss_ema')}, "
                  f"action_top1={p.get('action_top1')}")
            print(f"    next-experience MAE: {p.get('mae')}")
            print(f"    inference={p.get('inference_seconds')}s, "
                  f"train={p.get('train_seconds')}s")
            effect = p.get('brain_effect') or {}
            print(f"    synapses grown FROM predictions: "
                  f"{effect.get('synapses_from_predictions', 0)}")
        
        brain_stats = self.brain.get_statistics()
        print(f"\n  Brain Statistics:")
        print(f"    Total neurons: {brain_stats['total_neurons']}")
        print(f"    Connections: {brain_stats['total_connections']}")
        print(f"    Custom neurons: {brain_stats['custom_neurons']}")
        
        return {**self.stats, **brain_stats}
        
    # The perceptual sensor is local: food somewhere else in the tank does not
    # produce the same signal as food within reach. Positions are normalised.
    FOOD_SIGHT_RADIUS = 0.32
    FOOD_BITE_RADIUS = 0.055
    FOOD_SWIM_STEP = 0.085

    def _nearest_visible_food(self):
        if not self.food_items:
            return None
        x, y = self.squid.x, self.squid.y
        item = min(self.food_items,
                   key=lambda food: math.hypot(food['x'] - x, food['y'] - y))
        if math.hypot(item['x'] - x, item['y'] - y) <= self.FOOD_SIGHT_RADIUS:
            return item
        return None

    def _refresh_food_sense(self):
        self.squid.food_visible = self._nearest_visible_food() is not None

    def _food_percept(self):
        """Egocentric food percept for the predictive cortex: the
        direction of the nearest VISIBLE food normalised by the sight
        radius (so +1.0 = one sight-radius east), or (0, 0, 0) when
        nothing is visible. Derived from the same perceptual test as
        can_see_food, so the cortex never receives information the squid
        has not perceived."""
        food = self._nearest_visible_food()
        if food is None:
            return (0.0, 0.0, 0.0)
        return ((food['x'] - self.squid.x) / self.FOOD_SIGHT_RADIUS,
                (food['y'] - self.squid.y) / self.FOOD_SIGHT_RADIUS,
                1.0)

    def _move_randomly(self, distance=0.055):
        self.squid.x = max(0.0, min(1.0, self.squid.x + random.uniform(-distance, distance)))
        self.squid.y = max(0.0, min(1.0, self.squid.y + random.uniform(-distance, distance)))

    def _act_on_neural_decision(self, action):
        """Apply the decision to the *body* before observing its consequences.

        This is deliberately a small geometric aquarium, not a second
        behaviour policy. Action selection comes solely from the shared
        decision_engine.select_action function and actual neuron activations.
        """
        squid = self.squid
        squid.status = action

        if action == "eating":
            food = self._nearest_visible_food()
            if food is not None:
                dx, dy = food['x'] - squid.x, food['y'] - squid.y
                distance = math.hypot(dx, dy)
                if distance > self.FOOD_BITE_RADIUS:
                    step = min(self.FOOD_SWIM_STEP, distance)
                    squid.x += (dx / distance) * step
                    squid.y += (dy / distance) * step
                    squid.pursuing_food = True
                    self.stats['food_approaches'] += 1
                if math.hypot(food['x'] - squid.x, food['y'] - squid.y) <= self.FOOD_BITE_RADIUS:
                    self.food_items.remove(food)
                    squid.feed()
                    self.stats['food_eaten'] += 1
            # Desire to eat with nothing in sight never creates free food.
        elif action == "fleeing":
            squid.is_fleeing = True
            self.stats['flee_actions'] += 1
            self._move_randomly(distance=0.09)
            if squid.is_startled:
                squid.is_startled = False
                squid.anxiety = max(0.0, squid.anxiety - 7.0)
                self.stats['escaped_startles'] += 1
        elif action in ("sleeping", "exhausted"):
            if not squid.is_sleeping:
                squid.sleep_ticks = 20
            squid.is_sleeping = True
            squid.status = "sleeping" if action == "sleeping" else "exhausted"
        elif action == "exploring":
            self._move_randomly()
        elif action == "approaching_plant" and squid.plant_nearby:
            squid.anxiety = max(0.0, squid.anxiety - 1.0)

        # A startle that the animal does not flee from has a consequence,
        # rather than being merely an inert set of sensor bits.
        if squid.is_startled:
            # Sleep is not an invulnerability frame during a startle.
            squid.health = max(0.0, squid.health - 0.75)
            self.stats['unavoided_startle_ticks'] += 1

        self._refresh_food_sense()

    def _simulation_step(self):
        """Advance world -> perception -> brain -> action -> body consequence.

        New learning evidence at the following tick sees the outcome of this
        action. It cannot learn from randomly awarded food.
        """
        self.squid.update()
        self._update_environment()
        self._refresh_food_sense()
        if self.squid.food_visible:
            self.stats['food_seen_ticks'] += 1
        self.brain.advance_clock(1.0)
        before = self.squid.get_state_dict()
        self.brain.update_state(before)
        # The predictive cortex (research module; no-op when disabled)
        # scores the previous prediction, records this tick's percept, and
        # writes its prediction sensors BEFORE propagation, so the network
        # can act on anticipation rather than reaction. Registered sensors
        # are never overwritten by propagation.
        if self.predictive.enabled:
            self.predictive.begin_tick(self.tick, before, self._food_percept())
        self.brain.propagate(observe_learning=self.config.learning_enabled)

        if self.squid.is_sleeping:
            chosen = "sleeping"
        elif (self.brain.state.get("act_collapse", 0.0)
              >= ACTION_THRESHOLDS["act_collapse"]):
            chosen = "exhausted"
        else:
            chosen, _confidence, _urgency = select_action(
                self.brain.state, jitter=False)
            if chosen is None:
                # Only a brain with an active motor pathway gets to swim.
                motor = self.brain.state.get("act_move", 0.0)
                chosen = ("exploring" if "act_move" in self.brain.positions
                          and motor >= ACTION_THRESHOLDS["act_move"]
                          else "idle")

        # Record an action episode *before* its consequence. The causal
        # learner compares this pre-action state to a subsequent observed
        # state, rather than crediting the squid for a random food event.
        if self.config.learning_enabled:
            self.brain.causal_learning.on_action(chosen, self.brain.state)
        counts = self.stats['actions_selected']
        counts[chosen] = counts.get(chosen, 0) + 1
        self._act_on_neural_decision(chosen)

        # Complete the predictive cortex's experience record for this tick:
        # the action actually taken and the network's own activations.
        # Training happens only while learning is enabled (a frozen
        # evaluation freezes the transformer too); sleep replay piggybacks
        # on the brain's own consolidation window.
        if self.predictive.enabled:
            self.predictive.end_tick(chosen, self.brain.state)
            if self.config.learning_enabled:
                if self.tick % self.config.predictive_train_interval == 0:
                    self.predictive.train()
                if self.squid.is_sleeping:
                    self.predictive.sleep_replay()
                else:
                    self.predictive.on_wake()

        if self.config.learning_enabled:
            if self.tick % self.config.hebbian_interval == 0:
                updated = self.brain.perform_hebbian_learning()
                if updated:
                    self.stats['hebbian_updates'] += len(updated)
            self.brain.consolidate(self.squid.is_sleeping)
            new_neuron = self.brain.check_neurogenesis(
                self.squid.get_state_dict(), self.tick)
            if new_neuron:
                self.stats['neurons_created'] += 1
                print(f"  🧠 Tick {self.tick}: Created neuron '{new_neuron}'")

        self.stats['peak_anxiety'] = max(self.stats['peak_anxiety'], self.squid.anxiety)
        self.stats['peak_happiness'] = max(self.stats['peak_happiness'], self.squid.happiness)

    def _update_environment(self):
        """Spawn percepts and hazards, never hand the squid a free meal."""
        if random.random() < self.config.food_spawn_chance:
            self.food_items.append({'x': random.random(), 'y': random.random()})
        if random.random() < self.config.poop_spawn_chance:
            self.poop_items.append({'x': random.random(), 'y': random.random()})
            self.squid.cleanliness = max(0, self.squid.cleanliness - 5)
        if random.random() < self.config.startle_chance:
            self.squid.startle()
            self.stats['startles'] += 1
        self.squid.plant_nearby = random.random() < 0.2

    def _process_events(self):
        """Process queued scenario events"""
        events_to_remove = []
        
        for event in self.event_queue:
            if event.get('tick', 0) == self.tick:
                self._execute_event(event)
                events_to_remove.append(event)
                
        for event in events_to_remove:
            self.event_queue.remove(event)
            
    def _execute_event(self, event: Dict):
        """Apply a scripted event, marking non-neural interventions."""
        event_type = event.get('type', '')
        if event_type in ('feed', 'clean', 'set_state'):
            # Drop only unresolved credit assignments. Settled knowledge
            # persists, but a prior squid action cannot claim this reward.
            self.brain.causal_learning.discard_pending_outcomes(
                reason='scripted_' + event_type)
        
        if event_type == 'set_state':
            state = event.get('state', {})
            for key, value in state.items():
                if hasattr(self.squid, key):
                    setattr(self.squid, key, value)
            print(f"  📋 Tick {self.tick}: Set state {state}")
            
        elif event_type == 'feed':
            # Explicit human/environment intervention is not an earned meal.
            self.squid.feed()
            self.stats['manual_feedings'] += 1
            print(f"  🍕 Tick {self.tick}: Fed squid (external intervention)")
            
        elif event_type == 'startle':
            self.squid.startle()
            self.stats['startles'] += 1
            print(f"  ⚡ Tick {self.tick}: Startled squid")
            
        elif event_type == 'clean':
            self.squid.clean()
            print(f"  🧹 Tick {self.tick}: Cleaned environment")
            
        elif event_type == 'new_object':
            self.squid.curiosity = min(100, self.squid.curiosity + 20)
            print(f"  🆕 Tick {self.tick}: New object encountered")
            
    def _report_progress(self, tps: float):
        """Report training progress"""
        stats = self.brain.get_statistics()
        squid = self.squid
        
        progress_pct = (self.tick + 1) / max(1, self.stats.get('target_ticks', self.tick + 1)) * 100
        
        print(f"  [{self.tick+1:6d}] {tps:6.1f} t/s | "
              f"Neurons: {stats['total_neurons']:2d} | "
              f"H:{squid.hunger:5.1f} A:{squid.anxiety:5.1f} S:{squid.satisfaction:5.1f} | "
              f"Created: {self.stats['neurons_created']}")
              
    def stop(self):
        """Stop the simulation"""
        self.running = False


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Dosidicus-2 Headless Brain Trainer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Train a brain for 10000 ticks:
    python headless_trainer.py --brain my_brain.json --ticks 10000 --output trained.json
    
  Run a stress test scenario:
    python headless_trainer.py --brain my_brain.json --scenario stress_test --output stress_trained.json
    
  List available scenarios:
    python headless_trainer.py --list-scenarios
    
  Quick training with default brain:
    python headless_trainer.py --ticks 5000 --output quick_trained.json
        """
    )
    
    parser.add_argument('--brain', '-b', type=str, help='Path to brain JSON file to load')
    parser.add_argument('--seed', type=int,
                        help='Random seed. With one set the run is reproducible: '
                             'the same seed, brain and tick count give the same '
                             'trained brain every time.')
    parser.add_argument('--blank', action='store_true',
                        help='Start from a blank 8-neuron brain (the eight '
                             'required neurons, no synapses, no innate reflexes) '
                             'instead of the newborn brain a real squid gets. '
                             'The control condition for an experiment.')
    parser.add_argument('--output', '-o', type=str, help='Path to save trained brain')
    parser.add_argument('--ticks', '-t', type=int, default=10000, help='Number of ticks to train (default: 10000)')
    parser.add_argument('--scenario', '-s', type=str, help='Training scenario to use')
    parser.add_argument('--list-scenarios', action='store_true', help='List available training scenarios')
    parser.add_argument('--progress', '-p', type=int, default=500, help='Progress report interval (default: 500)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')
    
    # Config overrides
    parser.add_argument('--learning-rate', type=float, help='Hebbian learning rate')
    parser.add_argument('--neurogenesis', type=bool, help='Enable neurogenesis')
    parser.add_argument('--max-neurons', type=int, help='Maximum neurons allowed')

    # Predictive-cognition research module (off by default)
    parser.add_argument('--predictive', type=str, default='off',
                        choices=['off', 'linear', 'transformer'],
                        help="Attach the predictive cortex: 'off' (default, "
                             "baseline-identical), 'linear' (simple "
                             "smoothing control) or 'transformer' (small "
                             "temporal transformer predicting the next "
                             "experience and exposing predictions as senses)")
    parser.add_argument('--predictive-train-interval', type=int, default=64,
                        help='Ticks between predictive-cortex training batches')
    parser.add_argument('--predictive-save', type=str,
                        help='Save predictive-cortex weights to a JSON file after training')
    parser.add_argument('--predictive-load', type=str,
                        help='Load predictive-cortex weights from a JSON file before running')
    parser.add_argument('--predictive-report', type=str,
                        help='Write the predictive-cortex telemetry report to a JSON file')
    
    args = parser.parse_args()
    
    # List scenarios
    if args.list_scenarios:
        print("\nAvailable Training Scenarios:")
        print("-" * 60)
        for name, scenario in TRAINING_SCENARIOS.items():
            print(f"\n  {name}:")
            print(f"    {scenario.description}")
            print(f"    Duration: {scenario.duration_ticks} ticks")
            if scenario.config_overrides:
                print(f"    Config overrides: {scenario.config_overrides}")
        print()
        return
        
    # Build config
    config = TrainingConfig()
    if args.learning_rate:
        config.learning_rate = args.learning_rate
    if args.neurogenesis is not None:
        config.neurogenesis_enabled = args.neurogenesis
    if args.max_neurons:
        config.max_neurons = args.max_neurons
    if args.seed is not None:
        config.seed = args.seed
    if args.predictive:
        config.predictive_mode = args.predictive
    if args.predictive_train_interval:
        config.predictive_train_interval = args.predictive_train_interval
    if args.blank:
        config.blank = True
        
    # Create simulation
    sim = HeadlessSimulation(config)

    # Load predictive-cortex weights (after the cortex exists; must match
    # the observation layout the weights were trained on)
    if args.predictive_load and sim.predictive.enabled:
        if not sim.predictive.load_weights(args.predictive_load):
            print(f"✗ Could not load predictive weights: {args.predictive_load}")
            sys.exit(1)
    
    # Load brain
    if args.brain:
        if not os.path.exists(args.brain):
            print(f"✗ Brain file not found: {args.brain}")
            sys.exit(1)
        if not sim.load_brain(args.brain):
            sys.exit(1)
    else:
        print("ℹ Using default brain architecture")
        
    # Load scenario
    ticks = args.ticks
    if args.scenario:
        if not sim.load_scenario(args.scenario):
            sys.exit(1)
        # Use scenario duration if longer
        scenario = TRAINING_SCENARIOS.get(args.scenario)
        if scenario and scenario.duration_ticks > ticks:
            ticks = scenario.duration_ticks
            
    # Run training
    progress = 0 if args.quiet else args.progress
    sim.stats['target_ticks'] = ticks
    
    try:
        stats = sim.run(ticks=ticks, progress_interval=progress)
    except KeyboardInterrupt:
        print("\n\n⚠ Training interrupted by user")
        sim.stop()
        stats = sim.stats
        
    # Save output
    if args.output:
        sim.brain.save_brain(args.output)
    else:
        # Default output name
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        output_name = f"trained_brain_{timestamp}.json"
        sim.brain.save_brain(output_name)

    if args.predictive_save and sim.predictive.enabled:
        sim.predictive.save_weights(args.predictive_save)
    if args.predictive_report and sim.predictive.enabled:
        sim.predictive.save_report(args.predictive_report)

    print("\n✓ Done!")


if __name__ == '__main__':
    main()
