import random

SQUID_FACTS = [
    "Humboldt squid reach 5 feet mantle length",
    "Dosidicus Gigas is latin for Humboldt squid",
    "Squid have three hearts and blue blood!",
    "Instantly change color for camouflage",
    "Dosidicus lives only one to two years",
    "Jet propulsion allows fast swimming",
    "Release ink clouds to escape",
    "Vertical migrators 3000 feet daily",
    "Has a hard beak like a parrot!",
    "Fastest growing marine invertebrate",
    "Mantle grows up to 1.5 meters",
]

def get_random_fact():
    """Return a short, meaningful Humboldt squid fact"""
    return random.choice(SQUID_FACTS)