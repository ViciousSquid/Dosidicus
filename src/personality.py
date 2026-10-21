from enum import Enum 

class Personality(Enum):
    TIMID = "timid"
    ADVENTUROUS = "adventurous"
    LAZY = "lazy"
    ENERGETIC = "energetic"
    INTROVERT = "introvert"
    GREEDY = "greedy"
    STUBBORN = "stubborn"

# There is no rule here about who may start a fight. Whether a squid does is
# its own grown aggression neuron's (src/fighting.py); personality reaches it
# only through how the squid's network is wired and what it has lived through.


#: A stubborn squid holds off sleep while another need is stronger - but not
#: indefinitely: from this sleepiness on nothing keeps it awake (and at 100 it
#: falls asleep where it is), and exhaustion (act_collapse) is never resisted.
STUBBORN_SLEEP_LIMIT = 90.0

#: The thought it has when it does.
RESISTED_SLEEP = "Was tired but resisted sleep due to stubbornness"


def resists_sleep(personality, hunger: float, curiosity: float, anxiety: float,
                  sleepiness: float) -> bool:
    """Is a stubborn squid holding off sleep right now?

    Only while some other need is stronger than 55% - hunger, curiosity
    (x0.8) or anxiety (x0.6) - and only below STUBBORN_SLEEP_LIMIT.
    """
    if getattr(personality, 'value', personality) != Personality.STUBBORN.value:
        return False
    if float(sleepiness or 0.0) >= STUBBORN_SLEEP_LIMIT:
        return False
    return max(float(hunger or 0.0) / 100.0, float(curiosity or 0.0) / 100.0 * 0.8,
               float(anxiety or 0.0) / 100.0 * 0.6) > 0.55


def squid_resists_sleep(squid) -> bool:
    return resists_sleep(getattr(squid, 'personality', None), getattr(squid, 'hunger', 0.0),
                         getattr(squid, 'curiosity', 0.0), getattr(squid, 'anxiety', 0.0),
                         getattr(squid, 'sleepiness', 0.0))
