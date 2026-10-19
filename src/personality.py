from enum import Enum 

class Personality(Enum):
    TIMID = "timid"
    ADVENTUROUS = "adventurous"
    LAZY = "lazy"
    ENERGETIC = "energetic"
    INTROVERT = "introvert"
    GREEDY = "greedy"
    STUBBORN = "stubborn"

def can_initiate_fight(personality):
    """Timid squid may defend themselves, but never start a fight."""
    value = getattr(personality, "value", personality)
    return str(value).lower() != "timid"
