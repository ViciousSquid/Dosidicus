from personality_traits import register_personality

def adventurous_decision(squid):
    if squid.curiosity > 70:
        squid.status = "exploring new areas"
        squid.explore_environment()
    elif squid.anxiety < 30:
        squid.status = "seeking thrills"
        squid.pursue_moving_objects()
    else:
        squid.status = "feeling adventurous"
        squid.move_quickly()

ADVENTUROUS = register_personality(
    "ADVENTUROUS",
    adventurous_decision,
    {"curiosity": 1.5, "anxiety": 0.7}
)