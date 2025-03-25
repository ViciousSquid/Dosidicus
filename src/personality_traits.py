from enum import Enum
from .personality import Personality

personality_traits = {}

def register_personality(name, decision_function, attribute_modifiers):
    # Base goal-oriented modifiers
    base_modifiers = {
        "organization_urgency": 1.0,
        "rock_interaction_chance": 1.0,
        "plant_seeking_urgency": 1.0,
        "goal_persistence": 1.0
    }
    
    # Personality-specific overrides
    if name == Personality.ADVENTUROUS:
        base_modifiers.update({
            "organization_urgency": 1.8,
            "rock_interaction_chance": 2.2,
            "goal_persistence": 1.5,
            "exploration_bonus": 1.3
        })
    elif name == Personality.TIMID:
        base_modifiers.update({
            "organization_urgency": 0.6,
            "rock_interaction_chance": 0.4,
            "plant_seeking_urgency": 1.2,  # Timid squids prefer plants
            "goal_persistence": 0.7
        })
    elif name == Personality.LAZY:
        base_modifiers.update({
            "organization_urgency": 0.3,
            "rock_interaction_chance": 0.8,
            "goal_persistence": 0.5
        })
    elif name == Personality.ENERGETIC:
        base_modifiers.update({
            "organization_urgency": 1.5,
            "rock_interaction_chance": 1.7,
            "goal_persistence": 1.8
        })
    elif name == Personality.GREEDY:
        base_modifiers.update({
            "organization_urgency": 0.9,
            "rock_interaction_chance": 1.1,
            "food_seeking_priority": 2.0  # Overrides other goals when hungry
        })
    elif name == Personality.STUBBORN:
        base_modifiers.update({
            "organization_urgency": 1.2,
            "rock_interaction_chance": 0.3,
            "goal_persistence": 2.0  # Very persistent once committed
        })
    
    # Combine with passed modifiers
    attribute_modifiers.update(base_modifiers)
    
    personality_traits[name] = {
        "decision_function": decision_function,
        "attribute_modifiers": attribute_modifiers,
        "goal_weights": {
            "organize": base_modifiers["organization_urgency"],
            "interact": base_modifiers["rock_interaction_chance"],
            "clean": base_modifiers["plant_seeking_urgency"]
        }
    }
    return name

# Register all personality types
def register_all_personalities():
    register_personality(
        Personality.TIMID,
        lambda squid: squid.anxiety * 1.5,  # Decision function
        {"anxiety_growth": 1.3, "curiosity_growth": 0.7}
    )
    
    register_personality(
        Personality.ADVENTUROUS,
        lambda squid: squid.curiosity * 1.8,
        {"curiosity_growth": 1.5, "exploration_boost": 1.4}
    )
    
    register_personality(
        Personality.LAZY,
        lambda squid: squid.sleepiness * 1.2,
        {"energy_drain": 0.6, "movement_speed": 0.8}
    )
    
    register_personality(
        Personality.ENERGETIC,
        lambda squid: 100 - squid.sleepiness,
        {"energy_drain": 1.4, "movement_speed": 1.3}
    )
    
    register_personality(
        Personality.GREEDY,
        lambda squid: squid.hunger * 2.0,
        {"hunger_growth": 1.3, "satisfaction_decay": 1.2}
    )
    
    register_personality(
        Personality.STUBBORN,
        lambda squid: 100 if squid.hunger > 70 else 30,
        {"food_preference": "sushi", "adaptability": 0.3}
    )

register_all_personalities()