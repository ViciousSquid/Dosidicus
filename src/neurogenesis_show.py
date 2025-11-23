
import time
import random
from typing import Optional

class ShowmanNeurogenesis:
    """
    Wrapper around EnhancedNeurogenesis that keeps all the *real* logic
    but guarantees the player *sees* a neuron when something cool happens.
    """

    def __init__(self, real_enhanced_neurogenesis):
        self.en = real_enhanced_neurogenesis          # the real system
        self.config = self.en.config
        self.last_showman_creation = 0                # our own cooldown
        self.showman_cooldown = 15.0                  # seconds between "show" neurons
        self.name_pool = {
            'novelty': [
                "encountered_novel_object",   # saw something new
                "exploration_reward",         # payoff for investigating
                "novelty_approach",           # moves toward new thing
                "wonder_trigger",             # pure “what’s that?” spark
                "discovery_satisfaction"      # aha-feeling after exploring
            ],
            'stress':  [
                "anxiety_reduction",          # calm-down signal
                "stress_relief",              # general stress dump
                "panic_brake",                # emergency stop
                "threat_avoidance",           # steer away from danger
                "comfort_seeking"             # look for safe spots
            ],
            'reward':  [
                "food_reward",                # payoff for eating
                "cleanliness_reward",         # payoff for getting clean
                "rest_reward",                # payoff for sleeping
                "play_reward",                # payoff for fun interactions
                "achievement_reward"          # payoff for completing any goal
            ]
        }

    # -------------- public API – same as EnhancedNeurogenesis --------------

    def capture_experience_context(self, trigger, state, actions, env):
        # delegate to real system
        return self.en.capture_experience_context(trigger, state, actions, env)

    def should_create_neuron(self, ctx) -> bool:
        """
        1.  Ask the real system first.
        2.  If real system says YES → return YES (normal path).
        3.  If real system says NO → check whether *we* want to put on a show.
        """
        real_ok = self.en.should_create_neuron(ctx)
        if real_ok:
            return True

        # ---------- artistic license ----------
        now = time.time()
        if now - self.last_showman_creation < self.showman_cooldown:
            return False                                 # too soon for showmanship

        # decide whether this moment *deserves* a visible neuron
        if self._moment_deserves_neuron(ctx):
            print(f"🎭 Showman override – creating neuron for dramatic effect!")
            return True
        return False

    def create_functional_neuron(self, ctx) -> Optional[str]:
        """
        Create the neuron *through the real system* so it gets proper
        specialization, connections, utility, etc.
        We just sneak in a prettier name and a visual flourish.
        """
        # ask real system to do the heavy lifting
        real_name = self.en.create_functional_neuron(ctx)
        if real_name is None:
            return None

        # ---- cosmetic upgrade ----
        pretty_name = self._rename_for_drama(ctx.trigger_type, real_name)
        if pretty_name != real_name:
            # migrate everything to the new name
            self._migrate_neuron(real_name, pretty_name)

        # bigger, longer highlight for the player
        self.en.brain_widget.neurogenesis_highlight = {
            'neuron': pretty_name,
            'start_time': time.time(),
            'duration': 10.0,              # longer pulse
            'pulse_phase': 0,
            'is_emergency': False,
            'is_showman': True,            # flag for renderer (optional)
            'color_burst': self._burst_color(ctx.trigger_type)
        }
        self.last_showman_creation = time.time()
        return pretty_name

    # ------------------ internal helpers ------------------

    def _moment_deserves_neuron(self, ctx) -> bool:
        """
        Return True if this is a *visually* cool moment for the player.
        Keep the rules simple and transparent.
        """
        state = ctx.active_neurons
        env   = ctx.environmental_state

        # 1. first rock ever appears
        if env.get('has_rock') and ctx.recent_actions and 'rock' in ctx.recent_actions[-1]:
            return True

        # 2. first food after long hunger
        hunger = state.get('hunger', 50)
        if hunger > 85 and ctx.trigger_type == 'reward' and 'eat' in str(ctx.recent_actions):
            return True

        # 3. squid becomes *spotless* after being filthy
        cleanliness = state.get('cleanliness', 50)
        poop_count  = env.get('poop_count', 0)
        if cleanliness >= 95 and poop_count == 0 and ctx.trigger_type == 'reward':
            return True

        # 4. panic spike (anxiety 90+)
        anxiety = state.get('anxiety', 50)
        if anxiety >= 90 and ctx.trigger_type == 'stress':
            return True

        # 5. curiosity explosion (95+) on novelty
        curiosity = state.get('curiosity', 50)
        if curiosity >= 95 and ctx.trigger_type == 'novelty':
            return True

        return False

    def _rename_for_drama(self, trigger: str, old: str) -> str:
        """Pick a cinematic name that still encodes the specialization."""
        pool = self.name_pool[trigger]
        # keep pool unique per session
        used = {n for n in self.en.functional_neurons.keys() if n in pool}
        available = [n for n in pool if n not in used]
        if available:
            return available[0]
        # fallback – append digit so we never duplicate
        root = pool[0]
        counter = 2
        while f"{root}_{counter}" in self.en.functional_neurons:
            counter += 1
        return f"{root}_{counter}"

    def _migrate_neuron(self, old_name: str, new_name: str):
        """Move neuron data to the prettier name."""
        bw = self.en.brain_widget

        # positions
        bw.neuron_positions[new_name] = bw.neuron_positions.pop(old_name)
        # state
        bw.state[new_name] = bw.state.pop(old_name)
        # colours / shapes
        if old_name in getattr(bw, 'state_colors', {}):
            bw.state_colors[new_name] = bw.state_colors.pop(old_name)
        if old_name in getattr(bw, 'neuron_shapes', {}):
            bw.neuron_shapes[new_name] = bw.neuron_shapes.pop(old_name)

        # weights – rebuild keys
        new_weights = {}
        for (src, dst), w in bw.weights.items():
            src = new_name if src == old_name else src
            dst = new_name if dst == old_name else dst
            new_weights[(src, dst)] = w
        bw.weights = new_weights

        # functional_neurons dict
        self.en.functional_neurons[new_name] = self.en.functional_neurons.pop(old_name)
        self.en.functional_neurons[new_name].name = new_name

    def _burst_color(self, trigger: str) -> tuple:
        """Bright colour flash for the neuron birth."""
        return {
            'novelty': (255, 215, 0),   # gold
            'stress':  (255, 100, 100), # crimson
            'reward':  (100, 255, 100)  # mint
        }[trigger]

    # -------------- passthrough anything we don’t override --------------
    def __getattr__(self, item):
        return getattr(self.en, item)