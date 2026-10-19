"""Portable neuron actuator binding, shared by desktop and Android."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

class OutputTriggerMode(Enum):
    """How the output should be triggered."""
    THRESHOLD_RISING = "rising"      # Fire when crossing threshold upward
    THRESHOLD_FALLING = "falling"    # Fire when crossing threshold downward  
    THRESHOLD_ABOVE = "above"        # Fire continuously while above threshold
    THRESHOLD_BELOW = "below"        # Fire continuously while below threshold
    ON_CHANGE = "change"             # Fire on any significant change


@dataclass
class NeuronOutputBinding:
    """
    Binds a neuron to an output hook.
    
    When the neuron's activation meets the trigger conditions,
    the bound hook is fired with the activation value.
    """
    neuron_name: str
    output_hook: str
    threshold: float = 70.0
    trigger_mode: OutputTriggerMode = OutputTriggerMode.THRESHOLD_RISING
    cooldown: float = 1.0  # Seconds between firings
    enabled: bool = True

    # Chance the behaviour actually happens once the neuron has crossed its
    # threshold. 1.0 is a reflex that always fires; the ink cloud is 0.35,
    # which is what makes a startled squid SOMETIMES ink instead of always.
    # Keeping the chance on the binding makes it a visible, tunable property
    # of the reflex rather than a random.random() buried in a behaviour rule.
    probability: float = 1.0
    
    # Optional parameters passed to the hook
    hook_params: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state (not saved)
    last_fire_time: float = 0.0
    last_activation: float = 0.0
    
    def to_dict(self) -> dict:
        """Serialize for saving."""
        return {
            'neuron_name': self.neuron_name,
            'output_hook': self.output_hook,
            'threshold': self.threshold,
            'trigger_mode': self.trigger_mode.value,
            'cooldown': self.cooldown,
            'enabled': self.enabled,
            'probability': self.probability,
            'hook_params': self.hook_params,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NeuronOutputBinding':
        """Deserialize from saved data."""
        trigger_mode = OutputTriggerMode(data.get('trigger_mode', 'rising'))
        return cls(
            neuron_name=data['neuron_name'],
            output_hook=data['output_hook'],
            threshold=data.get('threshold', 70.0),
            trigger_mode=trigger_mode,
            cooldown=data.get('cooldown', 1.0),
            enabled=data.get('enabled', True),
            probability=float(data.get('probability', 1.0)),
            hook_params=data.get('hook_params', {}),
        )
    
    def should_fire(self, current_activation: float, current_time: float) -> bool:
        """Check if this binding should fire given current activation.

        NOTE: the cooldown is checked *after* the edge test, and the caller only
        advances last_activation once the edge has been evaluated. Checking the
        cooldown first (as this did) meant a rising-edge crossing that landed
        inside the cooldown window was swallowed instead of deferred, and the
        binding then never fired at all until the signal fell and rose again.
        """
        if not self.enabled:
            return False

        should_fire = False
        
        if self.trigger_mode == OutputTriggerMode.THRESHOLD_RISING:
            # Fire when crossing threshold upward
            should_fire = (
                self.last_activation < self.threshold and 
                current_activation >= self.threshold
            )
        
        elif self.trigger_mode == OutputTriggerMode.THRESHOLD_FALLING:
            # Fire when crossing threshold downward
            should_fire = (
                self.last_activation >= self.threshold and 
                current_activation < self.threshold
            )
        
        elif self.trigger_mode == OutputTriggerMode.THRESHOLD_ABOVE:
            # Fire continuously while above threshold
            should_fire = current_activation >= self.threshold
        
        elif self.trigger_mode == OutputTriggerMode.THRESHOLD_BELOW:
            # Fire continuously while below threshold
            should_fire = current_activation < self.threshold
        
        elif self.trigger_mode == OutputTriggerMode.ON_CHANGE:
            # Fire on significant change (>10% difference)
            should_fire = abs(current_activation - self.last_activation) > 10.0

        if not should_fire:
            return False

        # Edge established - now respect the cooldown. An edge suppressed here
        # is retried on the next evaluation because the caller holds
        # last_activation back until the binding is actually allowed to fire.
        if current_time - self.last_fire_time < self.cooldown:
            return False

        return True

    def is_edge_pending(self, current_activation: float) -> bool:
        """True when an edge exists but the cooldown is suppressing it."""
        if not self.enabled:
            return False
        if self.trigger_mode == OutputTriggerMode.THRESHOLD_RISING:
            return self.last_activation < self.threshold <= current_activation
        if self.trigger_mode == OutputTriggerMode.THRESHOLD_FALLING:
            return current_activation < self.threshold <= self.last_activation
        if self.trigger_mode == OutputTriggerMode.ON_CHANGE:
            return abs(current_activation - self.last_activation) > 10.0
        return False
