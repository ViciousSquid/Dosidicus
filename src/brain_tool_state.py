"""Reading the whole brain out of the Brain Tool window and putting one back:
what a save file holds, and what loading it restores.
"""
import logging
import time
import json
import random
from PyQt5 import QtWidgets

_LOG = logging.getLogger(__name__)


def split_connections(weights, neuron_positions, state):
    """A brain's connections, sorted for saving.

    Returns (between neurons, from a state, leading nowhere): the first two
    as [source, target, weight] lists, the third as "a -> b" names. A
    connection is "from a state" when its target is a neuron the brain has
    and its source is something the squid's state carries without a neuron
    for it (is_sick, is_eating...).
    """
    known = set(neuron_positions or ())
    carried = set(state or ())
    between, from_state, nowhere = [], [], []
    for key, value in (weights or {}).items():
        if not (isinstance(key, tuple) and len(key) == 2):
            print(f"Warning: Skipping non-standard weight key: {key}")
            continue
        source, target = key
        if source in known and target in known:
            between.append([source, target, value])
        elif target in known and source in carried:
            from_state.append([source, target, value])
        else:
            nowhere.append(f"{source} -> {target}")
    return between, from_state, nowhere


class BrainStateMixin:
    """Part of SquidBrainWindow (see brain_tool.py); not used on its own."""

    def get_brain_state(self):
        """
        Save brain state for persistence.
        
        IMPORTANT: Core neuron values (hunger, happiness, etc.) are NOT saved here.
        The squid object is the single source of truth for these values.
        Only non-core state (booleans, direction, position) and neurogenesis data are saved.
        """
        # Convert weights to a list for safe JSON serialization
        # A connection between two neurons this brain has goes in the brain's
        # own list. One FROM a state the squid has but no neuron for - the
        # sickness reflex wires is_sick -> cleanliness, and it does move the
        # squid's physiology (propagation.compute_neural_modulation) - is kept
        # beside it in 'state_connections': the brain format refuses a
        # connection to a neuron it was not given, and one such connection
        # used to stop the whole save and, from the autosave timer, the game.
        # Anything else that leads nowhere is left out and said so.
        weights_list, state_connections, strays = split_connections(
            self.brain_widget.weights, self.brain_widget.neuron_positions,
            self.brain_widget.state)
        if strays and strays != getattr(self, '_reported_stray_connections', None):
            self._reported_stray_connections = strays
            print(f"Not saved: {len(strays)} connection(s) to something that is not a "
                  f"neuron in this brain ({', '.join(strays[:5])})")

        # Core neurons whose values come from squid (single source of truth)
        core_stat_neurons = {'hunger', 'happiness', 'cleanliness', 'sleepiness',
                            'satisfaction', 'anxiety', 'curiosity'}

        # Save only non-core neuron states (booleans, direction, position, new neurons)
        # Core stat values will be synced from squid on load
        non_core_states = {}
        for key, value in self.brain_widget.state.items():
            if key not in core_stat_neurons:
                non_core_states[key] = value

        # Serialize full EnhancedNeurogenesis state (includes functional_neurons,
        # experience_buffer, counters, awarded_neurons, etc.)
        enhanced_neurogenesis_data = {}
        if hasattr(self.brain_widget, 'enhanced_neurogenesis'):
            try:
                enhanced_neurogenesis_data = self.brain_widget.enhanced_neurogenesis.to_dict()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"Warning: Could not serialize EnhancedNeurogenesis: {e}")

        # Output bindings were absent from this payload, so every neuron ->
        # behaviour binding the player made was dropped on save and then wiped
        # on load. brain_widget.output_bindings reads through to the live
        # NeuronOutputMonitor, which is the single source of truth.
        output_bindings = list(getattr(self.brain_widget, 'output_bindings', []) or [])

        # A squid's cognitive history is the point of the project, so it is
        # saved with the squid: why every synapse is the value it is, why every
        # grown neuron exists, what the squid has worked out about its own
        # actions, and what its network still cannot do.
        def _dump(attr):
            owner = getattr(self.brain_widget, attr, None)
            if owner is None or not hasattr(owner, 'to_dict'):
                return {}
            try:
                return owner.to_dict()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"Warning: could not serialize {attr}: {e}")
                return {}

        from .brain_io import desktop_brain_state
        return desktop_brain_state({
            **getattr(self.brain_widget, '_brain_document', {}),
            'weights_list': weights_list,
            'state_connections': state_connections,
            'clock': {'kind': 'wall', 'now': self.brain_widget.plasticity.clock()},
            'growth_clock': {'last_growth_at': self.brain_widget.enhanced_neurogenesis._last_growth_at,
                             'first_real_tick': self.brain_widget.enhanced_neurogenesis._first_real_tick},
            'neuron_shapes': dict(self.brain_widget.neuron_shapes),
            'neuron_positions': {str(k): v for k, v in self.brain_widget.neuron_positions.items()},
            'neuron_states': non_core_states,  # Only non-core states
            'neurogenesis_data': self.brain_widget.neurogenesis_data,
            'state_colors': getattr(self.brain_widget, 'state_colors', {}),
            'enhanced_neurogenesis': enhanced_neurogenesis_data,  # Full neurogenesis state
            'output_bindings': output_bindings,
            'provenance': _dump('ledger'),
            # Which neurons stand for which of the squid's own actions. Without
            # this a loaded brain would still have the neuron but nothing would
            # drive it, and a structure grown to resolve a confounded cause
            # would quietly stop working.
            'action_representations': dict(
                getattr(self.brain_widget, 'action_representations', {}) or {}),
            'causal_learning': _dump('causal_learning'),
            # What it has found out about its own actions: which it has tried
            # with and without which cue, and how each turned out.
            'action_discovery': _dump('action_discovery'),
            'capability': _dump('capability'),
            'plasticity': _dump('plasticity'),
            'consolidation': _dump('consolidation'),
            # Legacy key for backward compatibility (subset of enhanced_neurogenesis)
            'functional_neurons': enhanced_neurogenesis_data.get('functional_neurons', {})
        })

    def set_brain_state(self, state):
        """
        Load the brain state from a saved state dictionary.
        Uses robust fallback logic to handle missing keys and incomplete data.
        
        IMPORTANT: Core neuron values (hunger, happiness, etc.) are NOT loaded here.
        Call sync_state_from_squid() after this method to populate them from the squid.
        """
        from .brain_io import desktop_brain_state, normalise_brain
        from .brain_clock import rebase_cognitive_state
        if any(key in state for key in ('neurons', 'positions', 'neuron_positions')):
            state = rebase_cognitive_state(desktop_brain_state(state), self.brain_widget.plasticity.clock(), kind='wall')
            self.brain_widget._brain_document = normalise_brain(state)
            self.brain_widget.neuron_shapes = dict(state.get('neuron_shapes', {}))
            self.brain_widget.output_bindings = state.get('output_bindings', [])
            growth = self.brain_widget.enhanced_neurogenesis
            for key, attr in (('last_growth_at', '_last_growth_at'), ('first_real_tick', '_first_real_tick')):
                if key in state.get('growth_clock', {}):
                    setattr(growth, attr, state['growth_clock'][key])

        # Load weights (handle new list format and potentially old dict format)
        if 'weights_list' in state:
            weights = {}
            for item in state['weights_list']:
                if isinstance(item, list) and len(item) == 3:
                    weights[(item[0], item[1])] = item[2]
            # What the squid learned from a state it has no neuron for
            # (get_brain_state): back where propagation reads it.
            for item in state.get('state_connections') or []:
                if isinstance(item, (list, tuple)) and len(item) == 3 \
                        and isinstance(item[2], (int, float)):
                    weights[(str(item[0]), str(item[1]))] = float(item[2])
            self.brain_widget.weights = weights
        elif 'weights' in state:  # Fallback for old format (acknowledging its bug)
            print("Warning: Loading old 'weights' format. May cause issues with new neurons.")
            weights = {}
            for k, v in state['weights'].items():
                if '_' in k:
                    key = tuple(k.split('_'))  # This is the buggy part
                else:
                    key = k
                weights[key] = v
            self.brain_widget.weights = weights
        else:
            print("⚠️  No weights data in state, preserving current weights")

        # Load neuron positions, defaulting to original if not found
        self.brain_widget.neuron_positions = state.get('neuron_positions', self.brain_widget.original_neuron_positions.copy())

        # Load non-core neuron states (booleans, direction, position, new neuron values)
        loaded_states = state.get('neuron_states', {})
        self.brain_widget.state = loaded_states.copy()

        # Core stats are deliberately not saved (the squid owns them), so pull
        # them back in now. Nothing called sync_state_from_squid() before, which
        # left the brain with no core values at all until the first tick.
        squid = getattr(self.tamagotchi_logic, 'squid', None) if self.tamagotchi_logic else None
        if squid is not None:
            self.sync_state_from_squid(squid)

        # Load neurogenesis_data (basic tracking for brain_widget display)
        self.brain_widget.neurogenesis_data = state.get('neurogenesis_data', {
            'new_neurons': [], 'last_neuron_time': time.time(), 'new_neurons_details': {}
        })
        if 'new_neurons' not in self.brain_widget.neurogenesis_data:
            self.brain_widget.neurogenesis_data['new_neurons'] = []
        if 'new_neurons_details' not in self.brain_widget.neurogenesis_data:
            self.brain_widget.neurogenesis_data['new_neurons_details'] = {}

        # Load state colors (with fallback)
        self.brain_widget.state_colors = state.get('state_colors', {
            'is_sick': (255, 204, 204), 'is_eating': (204, 255, 204),
            'is_sleeping': (204, 229, 255), 'pursuing_food': (255, 229, 204),
            'direction': (229, 204, 255)
        })

        # =====================================================================
        # LOAD FULL EnhancedNeurogenesis STATE
        # =====================================================================
        if hasattr(self.brain_widget, 'enhanced_neurogenesis'):
            # Prefer new 'enhanced_neurogenesis' key with full state
            if 'enhanced_neurogenesis' in state:
                try:
                    self.brain_widget.enhanced_neurogenesis.from_dict(state['enhanced_neurogenesis'])
                    fn_count = len(self.brain_widget.enhanced_neurogenesis.functional_neurons)
                    print(f"✅ Loaded full EnhancedNeurogenesis state ({fn_count} functional neurons)")
                    
                    # If from_dict failed to load neurons, try direct loading
                    if fn_count == 0 and 'functional_neurons' in state['enhanced_neurogenesis']:
                        print("⚠️  from_dict returned 0 neurons, attempting direct load...")
                        self._direct_load_functional_neurons(state['enhanced_neurogenesis']['functional_neurons'])
                except Exception as e:
                    print(f"⚠️  Error loading EnhancedNeurogenesis: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fall back to legacy loading
                    self._load_legacy_functional_neurons(state)
            # Fallback: legacy 'functional_neurons' key only
            elif 'functional_neurons' in state:
                self._load_legacy_functional_neurons(state)
                print("ℹ️  Loaded legacy functional_neurons format")

        # =====================================================================
        # FORCIBLY REBUILD NEUROGENESIS NEURONS FROM functional_neurons OR state
        # =====================================================================
        self._force_rebuild_neurogenesis_neurons(state)
        self.brain_widget.experience_buffer = self.brain_widget.enhanced_neurogenesis.experience_buffer

        # Restore the cognitive history. Without this a loaded squid would have
        # an evolved brain and no idea why - "every save file becomes a
        # permanent cognitive history" only holds if the history is in the file.
        for key, attr in (('provenance', 'ledger'),
                          ('causal_learning', 'causal_learning'),
                          ('action_discovery', 'action_discovery'),
                          ('capability', 'capability'),
                          ('plasticity', 'plasticity'),
                          ('consolidation', 'consolidation')):
            payload = state.get(key)
            owner = getattr(self.brain_widget, attr, None)
            if not payload or owner is None or not hasattr(owner, 'from_dict'):
                continue
            try:
                owner.from_dict(payload)
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"⚠️  Could not restore {key}: {type(e).__name__}: {e}")

        for action, neuron in (state.get('action_representations') or {}).items():
            if neuron in self.brain_widget.neuron_positions:
                self.brain_widget.represent_action(str(action), str(neuron))

        # A brain grown before provenance existed, or one whose ledger did not
        # survive, still deserves an answer to "why does this neuron exist?".
        # Rebuild what can honestly be rebuilt from the neurons' own records.
        self._backfill_neuron_origins()

        # --- Critical Step: Ensure brain_widget consistency after loading ---
        all_neurons = list(self.brain_widget.neuron_positions.keys())
        new_neurons_list = self.brain_widget.neurogenesis_data.get('new_neurons', [])

        # Get config colors for new neurons
        cfg_appearance = self.config.neurogenesis.get('appearance', {})
        cfg_colors = cfg_appearance.get('colors', {})
        default_colors = {'novelty': (255, 255, 150), 'stress': (255, 150, 150), 'reward': (150, 255, 150)}

        for neuron in all_neurons:
            # Ensure all neurons exist in the state dictionary (default 50 for new neurons)
            if neuron not in self.brain_widget.state:
                self.brain_widget.state[neuron] = 50

            # Ensure all neurons exist in communication events
            if hasattr(self.brain_widget, 'communication_events') and neuron not in self.brain_widget.communication_events:
                self.brain_widget.communication_events[neuron] = 0

            # Ensure new neurons have a color entry
            if neuron in new_neurons_list and neuron not in self.brain_widget.state_colors:
                if neuron.startswith('novel'):
                    color = tuple(cfg_colors.get('novelty', default_colors['novelty']))
                elif neuron.startswith('stress'):
                    color = tuple(cfg_colors.get('stress', default_colors['stress']))
                elif neuron.startswith('reward'):
                    color = tuple(cfg_colors.get('reward', default_colors['reward']))
                else:
                    color = (200, 200, 200)
                self.brain_widget.state_colors[neuron] = color

        # Ensure all core neurons have their original positions if missing
        from .brain_constants import REQUIRED_NEURONS
        for name, pos in REQUIRED_NEURONS.items():
            if name not in self.brain_widget.neuron_positions:
                self.brain_widget.neuron_positions[name] = pos

        # Reveal all core neurons for loaded games
        self.brain_widget.reveal_all_core_neurons()
        
        # Trigger staggered link fade animation when loading a save
        if self.brain_widget.show_links:
            self.brain_widget._enable_links_after_reveal()
        self.brain_widget.update()

    def _backfill_neuron_origins(self):
        """Give grown neurons a birth record when the ledger has none.

        Only ever fills gaps - an existing record is never overwritten, because
        the original reason is the true one and a reconstruction is not.
        """
        ledger = getattr(self.brain_widget, 'ledger', None)
        engine = getattr(self.brain_widget, 'enhanced_neurogenesis', None)
        if ledger is None or engine is None:
            return
        for name, fn in getattr(engine, 'functional_neurons', {}).items():
            if name in ledger.origins:
                continue
            deficit = getattr(fn, 'origin_deficit', None) or {}
            ledger.record_neuron_birth(
                name=name,
                deficit_kind=deficit.get('kind', 'representation'),
                deficit_summary=deficit.get(
                    'summary',
                    f"grown before this squid kept provenance; it is a "
                    f"{fn.neuron_type} neuron specialising in "
                    f"{fn.specialization.replace('_', ' ')}"),
                evidence=deficit.get('evidence', {}),
                remedy=deficit.get('remedy', ''),
                wiring=[(name, target, float(weight), 'restored')
                        for (src, target), weight in self.brain_widget.weights.items()
                        if src == name][:8],
                neuron_type=fn.neuron_type,
                specialization=fn.specialization,
                display_name=fn.display_name,
                timestamp=fn.creation_context.timestamp)

    def _load_legacy_functional_neurons(self, state):
        """Fallback loader for old save format with only functional_neurons key."""
        from .neurogenesis import FunctionalNeuron
        
        functional_neurons_data = state.get('functional_neurons', {})
        restored_neurons = {}
        
        for name, data in functional_neurons_data.items():
            try:
                restored_neurons[name] = FunctionalNeuron.from_dict(data)
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"Warning: Could not restore neuron {name}: {e}")
                continue
        
        self.brain_widget.enhanced_neurogenesis.functional_neurons = restored_neurons
        print(f"Loaded {len(restored_neurons)} functional neurons (legacy format)")

    def _direct_load_functional_neurons(self, functional_neurons_data):
        """
        Directly load FunctionalNeuron objects from save data, bypassing from_dict.
        This is a fallback when the normal loading path fails.
        """
        from .neurogenesis import FunctionalNeuron, ExperienceContext
        
        if not functional_neurons_data:
            print("⚠️  No functional_neurons_data to load")
            return
        
        loaded_count = 0
        for name, data in functional_neurons_data.items():
            try:
                # Manually construct the FunctionalNeuron
                creation_ctx = data.get('creation_context', {})
                active_neurons_data = creation_ctx.get('active_neurons') or creation_ctx.get('brain_state', {})
                
                context = ExperienceContext(
                    trigger_type=creation_ctx.get('trigger_type', 'stress'),
                    active_neurons=active_neurons_data,
                    recent_actions=creation_ctx.get('recent_actions', []),
                    environmental_state=creation_ctx.get('environmental_state', {}),
                    outcome=creation_ctx.get('outcome', 'neutral'),
                    timestamp=creation_ctx.get('timestamp', time.time())
                )
                
                neuron = FunctionalNeuron(
                    name=data.get('name', name),
                    neuron_type=data.get('neuron_type', 'stress'),
                    creation_context=context
                )
                
                # Restore additional attributes
                neuron.specialization = data.get('specialization', neuron.specialization)
                neuron.activation_count = data.get('activation_count', 0)
                neuron.last_activated = data.get('last_activated', 0)
                neuron.utility_score = data.get('utility_score', 0.0)
                neuron.strength_multiplier = data.get('strength_multiplier', 1.0)
                
                self.brain_widget.enhanced_neurogenesis.functional_neurons[name] = neuron
                loaded_count += 1
                print(f"   ↪ Direct loaded: {name}")
                
            except Exception as e:
                print(f"⚠️  Failed to direct load {name}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"✅ Direct loaded {loaded_count} functional neurons")

    def _force_rebuild_neurogenesis_neurons(self, state=None):
        """
        Forcibly rebuild all neurogenesis neurons from functional_neurons data.
        This ensures neurons are properly drawn after loading a save.
        
        Args:
            state: Optional brain state dict to use as fallback data source
        """
        if not hasattr(self.brain_widget, 'enhanced_neurogenesis'):
            return
        
        functional_neurons = self.brain_widget.enhanced_neurogenesis.functional_neurons
        
        # If no functional neurons loaded, try to load directly from state
        if not functional_neurons and state:
            print("⚠️  No functional neurons in enhanced_neurogenesis, loading from state...")
            fn_data = None
            if 'enhanced_neurogenesis' in state and 'functional_neurons' in state['enhanced_neurogenesis']:
                fn_data = state['enhanced_neurogenesis']['functional_neurons']
            elif 'functional_neurons' in state:
                fn_data = state['functional_neurons']
            
            if fn_data:
                self._direct_load_functional_neurons(fn_data)
                functional_neurons = self.brain_widget.enhanced_neurogenesis.functional_neurons
        
        if not functional_neurons:
            print("⚠️  No functional neurons to rebuild")
            return
        
        core_neurons = {'hunger', 'happiness', 'cleanliness', 'sleepiness',
                        'satisfaction', 'anxiety', 'curiosity'}
        excluded = getattr(self.brain_widget, 'excluded_neurons', [])
        
        # Ensure neurogenesis_data structures exist
        if not hasattr(self.brain_widget, 'neurogenesis_data'):
            self.brain_widget.neurogenesis_data = {}
        self.brain_widget.neurogenesis_data.setdefault('new_neurons', [])
        self.brain_widget.neurogenesis_data.setdefault('new_neurons_details', {})
        
        # Ensure neuron_shapes exists
        if not hasattr(self.brain_widget, 'neuron_shapes'):
            self.brain_widget.neuron_shapes = {}
        
        rebuilt_count = 0
        
        for name, fn in functional_neurons.items():
            if name in core_neurons or name in excluded:
                continue
            
            rebuilt_count += 1
            
            # 1. Force add to new_neurons list
            if name not in self.brain_widget.neurogenesis_data['new_neurons']:
                self.brain_widget.neurogenesis_data['new_neurons'].append(name)
            
            # 2. Force add to new_neurons_details
            if name not in self.brain_widget.neurogenesis_data['new_neurons_details']:
                self.brain_widget.neurogenesis_data['new_neurons_details'][name] = {
                    'created_at': fn.creation_context.timestamp,
                    'trigger_type': fn.neuron_type,
                    'trigger_value_at_creation': 0,
                    'specialisation': fn.specialization
                }
            
            # 3. Force add to neuron_positions (calculate if missing)
            if name not in self.brain_widget.neuron_positions:
                # Calculate position based on functional connections
                all_neurons = list(self.brain_widget.neuron_positions.keys())
                connections = fn.get_functional_connections(all_neurons)
                
                if connections:
                    total_weight = 0
                    center_x, center_y = 0, 0
                    for target, weight in connections.items():
                        if target in self.brain_widget.neuron_positions:
                            pos = self.brain_widget.neuron_positions[target]
                            abs_weight = abs(weight)
                            center_x += pos[0] * abs_weight
                            center_y += pos[1] * abs_weight
                            total_weight += abs_weight
                    if total_weight > 0:
                        center_x /= total_weight
                        center_y /= total_weight
                        x = max(50, min(974, center_x + random.randint(-80, 80)))
                        y = max(50, min(668, center_y + random.randint(-80, 80)))
                        self.brain_widget.neuron_positions[name] = (x, y)
                    else:
                        self.brain_widget.neuron_positions[name] = (random.randint(100, 900), random.randint(100, 600))
                else:
                    self.brain_widget.neuron_positions[name] = (random.randint(100, 900), random.randint(100, 600))
                print(f"   ↪ Rebuilt position for {name}")
            
            # 4. Force add to state
            if name not in self.brain_widget.state:
                self.brain_widget.state[name] = 50.0
            
            # 5. Force add to visible_neurons
            if hasattr(self.brain_widget, 'visible_neurons'):
                self.brain_widget.visible_neurons.add(name)
            
            # 6. Force set shape based on neuron type
            shape_map = {'novelty': 'diamond', 'stress': 'square', 'reward': 'triangle'}
            self.brain_widget.neuron_shapes[name] = shape_map.get(fn.neuron_type, 'circle')
            
            # 7. Force set color based on type and specialization
            spec = fn.specialization
            if 'stress' in spec or 'anxiety' in spec:
                self.brain_widget.state_colors[name] = (255, 150, 150)
            elif 'reward' in spec or 'satisfaction' in spec:
                self.brain_widget.state_colors[name] = (150, 255, 150)
            elif 'investigation' in spec or 'exploration' in spec:
                self.brain_widget.state_colors[name] = (255, 215, 0)
            else:
                color_map = {'novelty': (255, 255, 150), 'stress': (255, 150, 150), 'reward': (173, 216, 230)}
                self.brain_widget.state_colors[name] = color_map.get(fn.neuron_type, (200, 200, 255))
            
            # 8. Force add to communication_events
            if hasattr(self.brain_widget, 'communication_events'):
                if name not in self.brain_widget.communication_events:
                    self.brain_widget.communication_events[name] = 0
            
            # 9. Ensure connections exist - ONLY for a neuron whose synapses
            #    were genuinely lost. Running this unconditionally meant every
            #    load bolted extra synapses onto the saved network (including
            #    edges pointing into sensors, which nothing can drive), so a
            #    brain drifted a little further from its design on each restart.
            from .brain_constants import NON_PROPAGATED_NEURONS, CORE_STAT_NEURONS
            has_synapses = any(src == name or dst == name
                               for (src, dst) in self.brain_widget.weights)
            if has_synapses:
                continue
            all_neurons = list(self.brain_widget.neuron_positions.keys())
            connections = fn.get_functional_connections(all_neurons)
            for target, weight in connections.items():
                if target in NON_PROPAGATED_NEURONS and target not in CORE_STAT_NEURONS:
                    continue  # never wire into a sensor
                if (name, target) not in self.brain_widget.weights:
                    self.brain_widget.apply_weight_change(
                        (name, target), value=weight, mechanism='neurogenesis',
                        detail={'note': f"restored at load: {name} came back from "
                                        f"the save file with no synapses at all"},
                        create=True, animate=False)
        
        if rebuilt_count > 0:
            print(f"🔧 Force rebuilt {rebuilt_count} neurogenesis neurons from save data")

    def sync_state_from_squid(self, squid):
        """
        Sync brain_widget.state with current squid stats.
        
        This makes the squid the single source of truth for core neuron values.
        Call this after set_brain_state() during game load.
        """
        if not squid:
            print("⚠️  Cannot sync: no squid provided")
            return
        
        # Core stats that come from squid
        self.brain_widget.state['hunger'] = squid.hunger
        self.brain_widget.state['happiness'] = squid.happiness
        self.brain_widget.state['cleanliness'] = squid.cleanliness
        self.brain_widget.state['sleepiness'] = squid.sleepiness
        self.brain_widget.state['satisfaction'] = squid.satisfaction
        self.brain_widget.state['anxiety'] = squid.anxiety
        self.brain_widget.state['curiosity'] = squid.curiosity
        
        # Boolean states from squid
        self.brain_widget.state['is_sick'] = squid.is_sick
        self.brain_widget.state['is_sleeping'] = getattr(squid, 'is_sleeping', False)
        self.brain_widget.state['is_eating'] = getattr(squid, 'is_eating', False)
        self.brain_widget.state['pursuing_food'] = getattr(squid, 'pursuing_food', False)
        self.brain_widget.state['is_startled'] = getattr(squid, 'is_startled', False)
        self.brain_widget.state['is_fleeing'] = getattr(squid, 'is_fleeing', False)
        self.brain_widget.state['direction'] = getattr(squid, 'squid_direction', 'up')
        self.brain_widget.state['position'] = (squid.squid_x, squid.squid_y)
        
        print("✅ Brain state synced from squid")

    def save_brain_state(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Brain State", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'w') as f:
                json.dump(self.brain_widget.state, f)

    def load_brain_state(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Brain State", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'r') as f:
                state = json.load(f)
            self.brain_widget.update_state(state)
