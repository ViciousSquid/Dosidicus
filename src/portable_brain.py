"""UI-independent brain adapter shared by desktop training and Android.

The cognitive algorithms live in the same src modules used by BrainWidget.
This class supplies their data surface without a Qt or Kivy dependency.
"""
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from .brain_constants import (
    CORE_STAT_NEURONS as CORE_NEURONS, INPUT_SENSORS as _INPUT_SENSOR_POSITIONS,
    INNATE_CONNECTIONS, INNATE_ACTION_WIRING, action_competition_wiring,
    ACTION_NEURONS, newborn_neurons, action_resting_level, is_network_driven,
)
from .propagation import ExternallyDriven, propagate
from .plasticity import PlasticityEngine, PlasticityConfig
from .capability import CapabilityMonitor
from .causal_learning import ActionOutcomeLedger
from .neural_provenance import CausalLedger, RecordedSynapses
from .consolidation import ConsolidationManager
from .neurogenesis import EnhancedNeurogenesis
from .learning import LearningConfig

INPUT_SENSORS = set(_INPUT_SENSOR_POSITIONS) | {"can_see_food"}

@dataclass
class TrainingConfig:
    """Configuration for headless training"""
    # Learning parameters
    learning_rate: float = 0.1
    weight_decay: float = 0.01
    max_hebbian_pairs: int = 2
    hebbian_interval: int = 30  # ticks between hebbian updates
    
    # Neurogenesis parameters
    neurogenesis_enabled: bool = True
    neurogenesis_cooldown: int = 60  # ticks
    max_neurons: int = 100
    novelty_threshold: float = 3.0
    stress_threshold: float = 1.2
    reward_threshold: float = 3.5
    
    # Simulation parameters
    decay_rate: float = 0.95
    noise_range: float = 0.5
    
    # Scenarios
    food_spawn_chance: float = 0.02
    poop_spawn_chance: float = 0.01
    startle_chance: float = 0.005

    # Reproducibility. With a seed set, a run is deterministic: the same seed,
    # brain and tick count produce the same trained brain, byte for byte. That
    # is what makes a result here something another person can check rather
    # than something they have to take your word for.
    seed: Optional[int] = None

    # Hatch with no synapses and only the eight required neurons, instead of
    # the full newborn brain with its innate reflexes. A blank brain is the
    # control condition: anything it ends up knowing, it learned here.
    blank: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrainingConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})



class HeadlessBrain(RecordedSynapses, ExternallyDriven):
    """
    Neural network brain without GUI dependencies.
    Handles state updates, Hebbian learning, and neurogenesis.
    """
    
    def __init__(self, config: TrainingConfig = None):
        self.config = config or TrainingConfig()

        # Neural state
        self.state: Dict[str, float] = {}
        self.weights: Dict[Tuple[str, str], float] = {}
        self.positions: Dict[str, Tuple[float, float]] = {}
        self.neuron_shapes: Dict[str, str] = {}
        self.state_colors: Dict[str, tuple] = {}

        # Custom neurons tracking
        self.custom_neurons: Set[str] = set()
        self.new_neurons: Set[str] = set()
        self.connector_neurons: Set[str] = set()
        self.visible_neurons: Set[str] = set()

        # Learning tracking
        self.last_hebbian_pairs: List[Tuple[str, str]] = []
        self.weight_history: List[Dict] = []

        # Neurogenesis tracking
        self.neurogenesis_data = {
            'new_neurons': [],
            'last_neuron_time': 0,
            'neurons_created': 0,
            'functional_neurons': {},
            'new_neurons_details': {},
        }
        self.neurogenesis_highlight = {'neuron': None, 'start_time': 0, 'duration': 0}
        self.communication_events: Dict[str, float] = {}
        self.weight_animations: List[Dict] = []
        self.excluded_neurons: List[str] = ['is_sick', 'is_eating', 'pursuing_food',
                                            'direction', 'is_sleeping']
        # Neurons written from outside the forward pass - see
        # src/propagation.ExternallyDriven.
        self.action_representations: Dict[str, str] = {}
        self.externally_driven: Set[str] = set()
        self.last_neurogenesis_tick = 0
        # One tick is one second of the squid's life. The trainer runs
        # thousands of them per real second, so every pacing rule expressed in
        # seconds reads this instead of the wall clock - otherwise a whole
        # training run finishes inside one growth cooldown and the brain can
        # never develop.
        self.sim_seconds = 0.0
        self.pruning_enabled = True
        self.tamagotchi_logic = None
        self.learning_rate = self.config.learning_rate

        # Output bindings (for behaviors)
        self.output_bindings: List[Dict] = []

        # ---- the engine, exactly as the game runs it ----------------------
        learning_config = LearningConfig()
        learning_config.hebbian['base_learning_rate'] = self.config.learning_rate
        learning_config.hebbian['weight_decay'] = self.config.weight_decay
        learning_config.neurogenesis['max_neurons'] = self.config.max_neurons
        learning_config.neurogenesis['cooldown'] = self.config.neurogenesis_cooldown
        self.learning_config = learning_config

        self.ledger = CausalLedger(self)
        self.capability = CapabilityMonitor(self)
        self.causal_learning = ActionOutcomeLedger(self)
        self.plasticity = PlasticityEngine(
            PlasticityConfig.from_learning_config(learning_config))
        self.consolidation = ConsolidationManager(self)
        self.enhanced_neurogenesis = EnhancedNeurogenesis(self, learning_config)
        self.enhanced_neurogenesis.clock = lambda: self.sim_seconds
        # The monitor reads the same simulated clock, so "a deficit must
        # persist for 20 seconds" means 20 simulated seconds rather than being
        # switched off - which is what the trainer used to have to do.
        self.capability.clock = lambda: self.sim_seconds
        self.causal_learning.clock = lambda: self.sim_seconds
        # Spike timing is the one mechanism that is ABOUT time. On the wall
        # clock a trainer stepping 1 500 ticks a second presents every spike as
        # arriving under a millisecond after the last, and STDP computes
        # exactly zero for every synapse.
        self.plasticity.clock = lambda: self.sim_seconds
        self.experience_buffer = self.enhanced_neurogenesis.experience_buffer

        # Initialize default state
        self._initialize_default_state()

    # ------------------------------------------------------------------
    # The surface the shared engine reads. A BrainWidget provides these
    # through Qt; here they are plain data and no-ops, which is the whole
    # point of keeping the engine Qt-free.
    # ------------------------------------------------------------------
    @property
    def neuron_positions(self) -> Dict[str, Tuple[float, float]]:
        """The engine's name for `positions`. One dict, two names."""
        return self.positions

    @neuron_positions.setter
    def neuron_positions(self, value):
        self.positions = value

    def update(self):
        pass

    def mark_render_dirty(self):
        pass

    def sync_connections_from_weights(self):
        pass

    def log_neurogenesis_event(self, neuron_name, event_type, reason=None, details=None):
        self.weight_history.append({'event': event_type, 'neuron': neuron_name,
                                    'details': details or {}, 'tick': time.time()})

    def is_connector_neuron(self, name: str) -> bool:
        from .brain_constants import is_social_neuron
        return name in self.connector_neurons or (
            self.neuron_shapes.get(name) == 'hexagon' and not is_social_neuron(name))

    def is_new_neuron(self, name: str, newness_duration_sec: float = 300) -> bool:
        return name in self.new_neurons

    def get_neuron_degree(self, name: str) -> int:
        return sum(1 for edge in self.weights if name in edge)

    def find_orphan_neurons(self) -> List[str]:
        connected = {n for edge in self.weights for n in edge}
        return [n for n in self.positions
                if n not in connected and n not in self.excluded_neurons]

    def add_weight_animation(self, *args, **kwargs):
        pass

    # apply_weight_change / remove_weight / explain_* come from
    # RecordedSynapses. The trainer used to carry its own copy of the write
    # path, which is the same duplication in miniature that this refactor
    # exists to remove.
    def _connector_neuron_names(self) -> Set[str]:
        return {name for name, fn in
                self.enhanced_neurogenesis.functional_neurons.items()
                if getattr(fn, 'neuron_type', '') == 'connector'}
        
    def _initialize_default_state(self):
        """Initialize with default neuron structure.

        Hatched from brain_constants.newborn_neurons(), the same definition the
        game uses, so "a brain trained without the GUI starts from the same
        place the squid does" stays true. This used to carry its own copy of
        the eight default positions, which silently stopped matching the game
        the moment a squid started hatching with action neurons - and a brain
        trained here would then have had no way to express a behaviour at all.
        """
        if self.config.blank:
            self._initialize_blank_state()
            return

        for name, pos in newborn_neurons().items():
            self.positions[name] = pos
            if name in CORE_NEURONS:
                self.state[name] = 50.0
            elif name in ACTION_NEURONS:
                self.state[name] = action_resting_level(name)
            elif name in INPUT_SENSORS:
                self.state[name] = 0.0
            else:
                self.state[name] = 50.0

        # The instincts of the species, from the one table that holds them.
        innate = (tuple(INNATE_CONNECTIONS) + tuple(INNATE_ACTION_WIRING)
                  + action_competition_wiring())
        for src, dst, weight in innate:
            if src in self.positions and dst in self.positions:
                self.apply_weight_change(
                    (src, dst), value=float(weight), mechanism='innate',
                    detail={'note': "this squid was born with it"}, create=True)
            
    def _initialize_blank_state(self):
        """The eight required neurons, no synapses, no instincts.

        The control condition for an experiment: a brain that has been given
        nothing, so that anything it is found to know at the end of a run was
        learned during that run. Contrast _initialize_default_state(), which
        hatches the newborn a real squid gets - reflexes included.
        """
        from src.brain_constants import REQUIRED_NEURONS

        for name, pos in REQUIRED_NEURONS.items():
            self.positions[name] = pos
            self.state[name] = 0.0 if name in INPUT_SENSORS else 50.0

    def load_brain(self, brain_data: Dict) -> bool:
        """Load a brain from dictionary (JSON structure)"""
        try:
            from .brain_io import normalise_brain
            from .brain_clock import rebase_cognitive_state
            original = normalise_brain(brain_data)
            self._brain_document = original
            source_clock = original.get('clock') or {}
            target_now = float(original.get('sim_time', source_clock.get('now', 0))) if source_clock.get('kind') == 'simulation' else 0.0
            brain_data = rebase_cognitive_state(original, target_now, kind='simulation')
            self.sim_seconds = target_now
            # Clear existing
            self.state.clear()
            self.weights.clear()
            self.positions.clear()
            self.custom_neurons.clear()
            
            # Load positions/neurons — accept both 'positions' (headless export)
            # and 'neurons' (Designer / game format).
            positions_raw = brain_data.get('positions', brain_data.get('neurons', {}))
            for name, pos in positions_raw.items():
                if isinstance(pos, dict):
                    # Designer format: {'position': [x, y], 'is_custom': bool}
                    # Headless export format: {'x': float, 'y': float, 'is_custom': bool}
                    if 'position' in pos:
                        p = pos['position']
                        self.positions[name] = (float(p[0]), float(p[1]))
                    elif 'x' in pos and 'y' in pos:
                        self.positions[name] = (float(pos['x']), float(pos['y']))
                    else:
                        self.positions[name] = (0.0, 0.0)
                    if pos.get('is_custom', False):
                        self.custom_neurons.add(name)
                elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    self.positions[name] = (float(pos[0]), float(pos[1]))
                else:
                    # Fallback: unknown shape — park at origin rather than
                    # storing a raw unsupported value.
                    self.positions[name] = (0.0, 0.0)
                    
                # Initialize state
                if name in CORE_NEURONS:
                    self.state[name] = 50.0
                elif name in INPUT_SENSORS:
                    self.state[name] = 0.0
                elif name in ACTION_NEURONS:
                    self.state[name] = action_resting_level(name)
                else:
                    self.state[name] = 50.0
                    self.custom_neurons.add(name)
                    
            # Load weights/connections
            # Accept list format (Designer) and dict format (headless export).
            weights_data = brain_data.get('weights', brain_data.get('connections', {}))
            if isinstance(weights_data, dict):
                for key, weight in weights_data.items():
                    # Handle string keys like "hunger,satisfaction" or "hunger->satisfaction"
                    if isinstance(key, str):
                        if '->' in key:
                            parts = key.split('->')
                        else:
                            parts = key.replace('(', '').replace(')', '').replace("'", "").split(',')
                        if len(parts) >= 2:
                            src = parts[0].strip()
                            dst = parts[1].strip()
                            self.weights[(src, dst)] = float(weight)
                    else:
                        self.weights[tuple(key)] = float(weight)
            elif isinstance(weights_data, list):
                for conn in weights_data:
                    if isinstance(conn, dict):
                        src = conn.get('source', conn.get('from', ''))
                        dst = conn.get('target', conn.get('to', ''))
                        w = conn.get('weight', 0.5)
                        if src and dst:
                            self.weights[(src, dst)] = float(w)
                    elif isinstance(conn, (list, tuple)) and len(conn) >= 2:
                        self.weights[(conn[0], conn[1])] = float(conn[2]) if len(conn) > 2 else 0.5
                        
            self.state.update(brain_data['state'])
            # Load the brain's account of itself, so a loaded brain can still
            # be asked why it is the way it is.
            self._load_provenance(brain_data)

            # Load shapes
            self.neuron_shapes = brain_data.get('neuron_shapes', {})
            
            # Load output bindings
            self.output_bindings = brain_data.get('output_bindings', [])

            self.action_representations = {}
            self.externally_driven = set()
            for action, neuron in (brain_data.get('action_representations') or {}).items():
                if neuron in self.positions:
                    self.represent_action(str(action), str(neuron))
            
            # Load neurogenesis data if present
            if 'neurogenesis_data' in brain_data:
                self.neurogenesis_data.update(brain_data['neurogenesis_data'])
                
            growth = brain_data.get('enhanced_neurogenesis')
            if growth is None and 'functional_neurons' in brain_data:
                growth = {'functional_neurons': brain_data['functional_neurons']}
            if growth is not None:
                self.enhanced_neurogenesis.from_dict(growth)
                self.experience_buffer = self.enhanced_neurogenesis.experience_buffer
            for key, attr in (('last_growth_at', '_last_growth_at'), ('first_real_tick', '_first_real_tick')):
                if key in brain_data.get('growth_clock', {}):
                    setattr(self.enhanced_neurogenesis, attr, brain_data['growth_clock'][key])
            self.last_neurogenesis_tick = brain_data.get('last_neurogenesis_tick', 0)
            self.new_neurons = set(self.neurogenesis_data.get('new_neurons', []))
            self.capability._decay_last = self.sim_seconds
            print(f"✓ Loaded brain: {len(self.positions)} neurons, {len(self.weights)} connections")
            return True
            
        except Exception as e:
            print(f"✗ Error loading brain: {e}")
            return False
            
    def load_brain_file(self, filepath: str) -> bool:
        """Load brain from JSON file"""
        try:
            from .brain_io import read_brain_file
            return self.load_brain(read_brain_file(filepath))
        except Exception as e:
            print(f"✗ Error loading brain file: {e}")
            return False
            
    def export_brain(self) -> Dict:
        """
        Export brain in the Designer/game format understood by
        custom_brain_loader.BrainLoader._parse() (Format 2: neurons dict +
        connections list).  This ensures trained brains can be loaded
        straight back into the game without any manual conversion.
        """
        # neurons dict — position as list, is_custom flag
        neurons = {}
        for name, pos in self.positions.items():
            neurons[name] = {
                **getattr(self, '_brain_document', {}).get('neurons', {}).get(name, {}),
                'position': [pos[0], pos[1]],
                'is_custom': name in self.custom_neurons,
                'activation': self.state.get(name, 0.0),
            }

        # connections as a list of {source, target, weight} dicts
        # (BrainLoader._parse() Format 2 expects this exact structure)
        connections = []
        for (src, dst), w in self.weights.items():
            connections.append({'source': src, 'target': dst, 'weight': float(w)})

        return {
            **getattr(self, '_brain_document', {}),
            'format': 'brain_designer',
            'clock': {'kind': 'simulation', 'now': self.sim_seconds},
            'sim_time': self.sim_seconds,
            'growth_clock': {'last_growth_at': self.enhanced_neurogenesis._last_growth_at,
                             'first_real_tick': self.enhanced_neurogenesis._first_real_tick},
            'last_neurogenesis_tick': self.last_neurogenesis_tick,
            'enhanced_neurogenesis': self.enhanced_neurogenesis.to_dict(),
            'functional_neurons': {n: fn.to_dict() for n, fn in self.enhanced_neurogenesis.functional_neurons.items()},
            'metadata': {
                **getattr(self, '_brain_document', {}).get('metadata', {}),
                'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'exported_by': 'headless_trainer',
                'neuron_count': len(self.positions),
                'connection_count': len(self.weights),
                'custom_neuron_count': len(self.custom_neurons),
            },
            # ── game-loader-compatible keys ──────────────────────────────────
            'neurons': neurons,        # _parse() checks for 'neurons' key
            'connections': connections, # _parse() Format 2: list of dicts
            # ────────────────────────────────────────────────────────────────
            'neuron_shapes': dict(self.neuron_shapes),
            # Which neurons stand for which of the squid's own actions. A brain
            # that grew one of these to resolve a confounded cause needs it, or
            # the neuron arrives with nothing driving it.
            'action_representations': dict(self.action_representations),
            'output_bindings': self.output_bindings,
            'state': {k: v for k, v in self.state.items()},
            'neurogenesis_data': {
                **self.neurogenesis_data,
                'neurons_created': self.neurogenesis_data.get('neurons_created', 0),
                'stress_neurons':  self.stress_neuron_count,
                'novelty_neurons': self.novelty_neuron_count,
                'reward_neurons':  self.reward_neuron_count,
            },
            # The brain's account of ITSELF, under the same keys the game's
            # save uses. Without these a brain trained here arrives with an
            # evolved network and no idea why any of it is the way it is: you
            # could read its weights but not ask it what it learned, from what
            # experience, or what it still cannot do. For a trainer whose whole
            # point is producing brains other people examine, that is the more
            # important half of the file.
            **self._export_provenance(),
        }

    _PROVENANCE_PARTS = (
        ('provenance', 'ledger'),
        ('causal_learning', 'causal_learning'),
        ('capability', 'capability'),
        ('plasticity', 'plasticity'),
        ('consolidation', 'consolidation'),
    )

    def _export_provenance(self) -> Dict:
        """Serialise every part of the brain that can explain itself."""
        out = {}
        for key, attribute in self._PROVENANCE_PARTS:
            owner = getattr(self, attribute, None)
            if owner is None or not hasattr(owner, 'to_dict'):
                continue
            try:
                out[key] = owner.to_dict()
            except Exception as exc:
                print(f"⚠️  Could not export {key}: {type(exc).__name__}: {exc}")
        return out

    def _load_provenance(self, brain_data: Dict) -> None:
        """Restore the brain's account of itself from a file."""
        for key, attribute in self._PROVENANCE_PARTS:
            payload = brain_data.get(key)
            owner = getattr(self, attribute, None)
            if not payload or owner is None or not hasattr(owner, 'from_dict'):
                continue
            try:
                owner.from_dict(payload)
            except Exception as exc:
                print(f"⚠️  Could not restore {key}: {type(exc).__name__}: {exc}")
        
    def save_brain(self, filepath: str) -> bool:
        """Save brain to JSON file"""
        try:
            brain_data = self.export_brain()
            with open(filepath, 'w') as f:
                json.dump(brain_data, f, indent=2)
            print(f"✓ Saved brain to {filepath}")
            return True
        except Exception as e:
            print(f"✗ Error saving brain: {e}")
            return False
            
    def advance_clock(self, seconds: float = 1.0) -> float:
        """One tick is one second of the squid's life.

        Everything paced in seconds - growth cooldowns, how long a deficit must
        persist - reads this rather than the wall clock, so a run of 100 000
        ticks is a hundred thousand seconds of living even though it finishes
        in under a minute.
        """
        self.sim_seconds += float(seconds)
        return self.sim_seconds

    def update_state(self, squid_state: Dict[str, Any]):
        """Update brain state from squid state"""
        for key, value in squid_state.items():
            if key in self.positions or key in self.state:
                if isinstance(value, bool):
                    self.state[key] = 100.0 if value else 0.0
                elif isinstance(value, (int, float)):
                    self.state[key] = float(value)
                    
    def propagate(self):
        """One timestep, through the project's single transfer function."""
        # Neurons the world writes go first, then learning evidence, exactly
        # as BrainWidget does it, so a brief event contributes to the next
        # commit instead of being invisible.
        self.drive_external_neurons()
        self.observe_for_learning()

        targets = [n for n in self.positions
                   if is_network_driven(n) and n not in self.excluded_neurons
                   and n not in self.externally_driven]
        if not targets:
            return {}

        strengths = {name: getattr(fn, 'strength_multiplier', 1.0)
                     for name, fn in
                     self.enhanced_neurogenesis.functional_neurons.items()}
        return propagate(self.state, self.weights, targets, strengths=strengths)

    def compute_neural_modulation(self, gain: float = 0.30):
        from .propagation import compute_neural_modulation
        return compute_neural_modulation(self.state, self.weights, gain, self.ledger)

    def observe_for_learning(self) -> int:
        """Feed one tick of evidence to every learning mechanism."""
        try:
            self.capability.observe(self.state)
        except Exception:
            pass
        try:
            self.causal_learning.on_tick(self.state)
        except Exception:
            pass
        candidates = self.plasticity.eligible_neurons(
            self.positions.keys(), self.excluded_neurons,
            self._connector_neuron_names())
        return self.plasticity.observe(self.state, candidates)

    def perform_hebbian_learning(self) -> List[Tuple[str, str]]:
        """Commit one plasticity cycle, using the game's own rule.

        The old body scored pairs by v1 + v2 + random noise and applied
        delta = lr * (v1/100) * (v2/100), which is never negative - so a brain
        trained here could not develop a single inhibitory synapse, and an
        avoidance behaviour IS an inhibitory synapse.
        """
        result = self.plasticity.commit(
            weights=self.weights,
            neuron_names=list(self.positions.keys()),
            excluded=self.excluded_neurons,
            connectors=self._connector_neuron_names(),
            new_neurons=self.new_neurons,
            externally_driven=self.externally_driven)

        updated = []
        for edge, update in (result.get('weight_updates') or {}).items():
            mechanism = 'stdp' if abs(update.get('stdp_delta', 0.0) or 0.0) > \
                abs(update.get('hebbian_delta', 0.0) or 0.0) else 'hebbian'
            if self.apply_weight_change(
                    edge, value=update['new_weight'], mechanism=mechanism,
                    detail={'correlation': update.get('mean_covariance'),
                            'samples': update.get('samples'),
                            'hebbian_delta': update.get('hebbian_delta'),
                            'stdp_delta': update.get('stdp_delta'),
                            'stdp_direction': update.get('stdp_direction')},
                    create=True):
                updated.append(edge)
                self.weight_history.append({
                    'pair': edge, 'old': update['old_weight'],
                    'new': update['new_weight'], 'tick': time.time()})

        self.last_hebbian_pairs = [tuple(sorted(e)) for e in updated]
        return updated

    def consolidate(self, is_sleeping: bool):
        """Sleep replay and synaptic homeostasis, same engine as the game."""
        try:
            return self.consolidation.on_tick(is_sleeping, self.state)
        except Exception:
            return None

    def check_neurogenesis(self, squid_state: Dict, tick: int) -> Optional[str]:
        """Grow structure when the network persistently cannot cope.

        The old body asked "is anxiety over 70? is curiosity over 75?" - a
        fourth copy of the event thresholds the game has since abandoned. It
        now asks the same question the game does, through the same monitor and
        the same engine: what can this network not represent, regulate or
        express?
        """
        if not self.config.neurogenesis_enabled:
            return None

        if tick - self.last_neurogenesis_tick < self.config.neurogenesis_cooldown:
            return None

        try:
            self.capability.evaluate()
        except Exception as exc:
            print(f"[Capability] evaluation failed: {type(exc).__name__}: {exc}")
            return None

        engine = self.enhanced_neurogenesis
        deficit = engine.find_deficit(self.state)
        if deficit is None:
            return None

        context = engine.capture_experience_context(
            trigger_type=deficit.suggested_type,
            brain_state=self.state,
            recent_actions=[squid_state.get('status', 'roaming')],
            environment={'headless': True})
        # Pass the diagnosis through rather than letting the engine re-run it,
        # exactly as BrainWidget.check_neurogenesis_triggers does. A second
        # reading of a state that has moved on could disagree with the first,
        # and then the birth record would name a different deficit from the one
        # that actually justified the growth.
        if not engine.should_create_neuron(context, deficit=deficit):
            return None

        name = engine.create_functional_neuron(context, deficit=deficit)
        if name:
            self.last_neurogenesis_tick = tick
            self.custom_neurons.add(name)
            self.new_neurons.add(name)
            self.neurogenesis_data['neurons_created'] = \
                self.neurogenesis_data.get('neurons_created', 0) + 1
            if name not in self.neurogenesis_data['new_neurons']:
                self.neurogenesis_data['new_neurons'].append(name)
        return name

    # Counts are derived from the engine so they can never drift out of step
    # with the neurons that actually exist.
    def _count_type(self, neuron_type: str) -> int:
        return sum(1 for fn in self.enhanced_neurogenesis.functional_neurons.values()
                   if getattr(fn, 'neuron_type', '') == neuron_type)

    @property
    def stress_neuron_count(self) -> int:
        return self._count_type('stress')

    @property
    def novelty_neuron_count(self) -> int:
        return self._count_type('novelty')

    @property
    def reward_neuron_count(self) -> int:
        return self._count_type('reward')

    def _create_neuron(self, neuron_type: str, context: Dict) -> Optional[str]:
        """Delegate to the one creation path.

        The old body invented its own names, shapes and a fixed three-synapse
        wiring pattern per type, none of which matched what the game builds -
        so a neuron grown during training was a different kind of object from
        one grown in play.
        """
        name = self.enhanced_neurogenesis.create_neuron(
            neuron_type, brain_state=dict(self.state), environment=context or {})
        if name:
            self.custom_neurons.add(name)
            self.new_neurons.add(name)
        return name

    def _get_neuron_value(self, val) -> float:
        """Convert value to float for calculations"""
        if isinstance(val, bool):
            return 100.0 if val else 0.0
        if isinstance(val, (int, float)):
            return float(val)
        return 0.0
        
    def get_statistics(self) -> Dict:
        """Get brain statistics"""
        return {
            'total_neurons': len(self.positions),
            'total_connections': len(self.weights),
            'custom_neurons': len(self.custom_neurons),
            'stress_neurons': self.stress_neuron_count,
            'novelty_neurons': self.novelty_neuron_count,
            'reward_neurons': self.reward_neuron_count,
            'weight_updates': len(self.weight_history),
            'avg_weight': sum(self.weights.values()) / len(self.weights) if self.weights else 0,
        }

