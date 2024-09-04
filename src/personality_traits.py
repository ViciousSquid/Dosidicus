personality_traits = {}

def register_personality(name, decision_function, attribute_modifiers):
    personality_traits[name] = {
        "decision_function": decision_function,
        "attribute_modifiers": attribute_modifiers
    }
    return name