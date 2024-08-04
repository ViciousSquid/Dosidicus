from personality_traits import register_personality

def lazy_decision(squid):
    if squid.sleepiness > 50:
        squid.status = "taking a nap"
        squid.go_to_sleep()
    else:
        squid.status = "lounging around"
        squid.move_slowly()

LAZY = register_personality(
    "LAZY",
    lazy_decision,
    {"sleepiness": 1.5, "hunger": 0.8}
)