from personality_traits import register_personality

def introvert_decision(squid):
    if squid.happiness > 70:
        squid.status = "content in solitude"
        squid.move_slowly()
    else:
        squid.status = "seeking quiet corner"
        squid.move_towards_plant()

INTROVERT = register_personality(
    "INTROVERT",
    introvert_decision,
    {"happiness": 1.2, "anxiety": 0.8}
)