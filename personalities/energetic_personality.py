from personality_traits import register_personality

def energetic_decision(squid):
    if squid.happiness > 80:
        squid.status = "excitedly swimming around"
        squid.move_quickly()
    elif squid.hunger < 30:
        squid.status = "energetically searching for food"
        squid.search_for_food()
    else:
        squid.status = "feeling energetic"
        squid.explore_environment()

ENERGETIC = register_personality(
    "ENERGETIC",
    energetic_decision,
    {"happiness": 1.2, "hunger": 0.8}
)