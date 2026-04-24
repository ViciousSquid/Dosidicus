import random

SQUID_FACTS = [
    "Dosidicus Gigas: scientific name for Humboldt squid",
    "Humboldt squid can reach a mantle length of 1.5 m (5 ft)",
    "Cephalopods have a hard beak like a parrot!",
    "Cephalopod blood is blue because it is copper-based",
    "These predators thrive in the `Oxygen Minimum Zone.`",
    "A squid's beak is the only rigid part of its body.",
    "Some squids have reached speeds of 25 km/h!",
    "Cannibalism occurs among the species when food is scarce.",
    "The Kraken is a legendary, ship-sinking gigantic squid",
    "Cephalopods are the fastest growing marine invertebrate",
    "Giant Squid can grow to 30-foot-long in just a few years",
    "Squids use jet propulsion to move quickly through the water",
    "Squids breathe using gills located inside their mantle",
]

def get_random_fact():
    """Return a squid fact"""


    return random.choice(SQUID_FACTS)
