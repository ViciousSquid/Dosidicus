# File: lifecycle.py
"""A squid's life after it has reproduced: the parent, its egg, and the hatch.

Reproduction only ever happens in a multiplayer encounter, and only the host
tank decides that it happened (see plugins/multiplayer/host_body.py). What
follows from it is not a multiplayer concern at all - it is a fact about this
tank and this squid, and it has to keep happening whether or not the plugin is
still loaded, so it lives here, in the core, and is written into the save.

    living  --reproduced-->  parent  --starved-->  dead
                               |                    |
                             egg laid           egg hatches -> a new squid

Three rules hold the whole thing together:

  * ONE RECORD. The parent's state and the egg are written in one object and
    therefore in one save. They cannot be persisted separately, so a crash can
    never leave a starving parent with no egg, or an egg with a parent that is
    still eating.

  * EVERY TRANSITION IS GUARDED BY THE STATE IT LEAVES. Each method returns
    True only when it actually moved the lifecycle on. Calling it again - a
    retransmitted message, a second timer, a reload - finds the state already
    moved and does nothing. `dead` is terminal.

  * NOTHING HERE IS A SECOND METABOLISM. A parent that has stopped eating gets
    hungry through the same hunger rise every squid has; the only addition is
    that, once it is starving, the health loss the tank already computes is
    actually applied to it. A squid that has not reproduced is untouched.

The mate is recorded by its persistent identity (uuid and display name), which
is what the wire already carries. Nothing about the other squid's mind is, or
could be, stored here.
"""

import re
import time
from typing import Any, Dict, Optional

STAGE_LIVING = 'living'
STAGE_PARENT = 'parent'
STAGE_DEAD = 'dead'
STAGES = (STAGE_LIVING, STAGE_PARENT, STAGE_DEAD)

EGG_INCUBATING = 'incubating'
EGG_HATCHING = 'hatching'
EGG_STATES = (EGG_INCUBATING, EGG_HATCHING)

#: Defaults for config.ini [Lifecycle]. See ConfigManager.get_lifecycle_config.
DEFAULT_CONFIG = {
    # Chance that one sustained contact during a visit is a mating. Rolled at
    # most once per visit, so a brief brush past never counts.
    'mating_chance': 0.02,
    # Seconds the two bodies must stay in reach before that roll happens.
    'mating_contact_seconds': 5.0,
    # Hunger at or above which a parent is starving and starts losing health.
    # The same line the mobile engine draws (STARVE_HUNGER).
    'starvation_hunger': 90.0,
}

_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def is_valid_mating_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


class Lifecycle:
    """One squid's reproductive lifecycle, and the egg it leaves in its tank."""

    __slots__ = ('stage', 'reproduction', 'egg')

    def __init__(self):
        self.stage = STAGE_LIVING
        #: {'mating_id', 'mate_uuid', 'mate_name', 'at'} once it has happened.
        self.reproduction: Optional[Dict[str, Any]] = None
        #: {'egg_id', 'state', 'laid_at', 'x', 'y'} while there is an egg.
        self.egg: Optional[Dict[str, Any]] = None

    # -- reading --------------------------------------------------------
    @property
    def can_eat(self) -> bool:
        return self.stage == STAGE_LIVING

    @property
    def can_reproduce(self) -> bool:
        return self.stage == STAGE_LIVING and self.egg is None

    @property
    def can_visit(self) -> bool:
        """A parent stays with its egg; a dead squid goes nowhere."""
        return self.stage == STAGE_LIVING

    @property
    def is_dead(self) -> bool:
        return self.stage == STAGE_DEAD

    @property
    def mating_id(self) -> str:
        return (self.reproduction or {}).get('mating_id', '')

    @property
    def mate_uuid(self) -> str:
        return (self.reproduction or {}).get('mate_uuid', '')

    @property
    def egg_state(self) -> str:
        return (self.egg or {}).get('state', '')

    # -- transitions ----------------------------------------------------
    def record_reproduction(self, mating_id: str, mate_uuid: str,
                            mate_name: str = "Squid", x: float = 0.0,
                            y: float = 0.0, now: Optional[float] = None) -> bool:
        """living -> parent, and the egg is laid. True only the first time.

        A repeat of the same event (the same mating id) and any second event
        (a squid reproduces once) are both refused, which is what makes a
        retransmitted or replayed mating unable to lay a second egg.
        """
        if not is_valid_mating_id(mating_id) or not mate_uuid:
            return False
        if self.mating_id == mating_id or not self.can_reproduce:
            return False
        stamp = float(now if now is not None else time.time())
        self.stage = STAGE_PARENT
        self.reproduction = {
            'mating_id': mating_id,
            'mate_uuid': str(mate_uuid),
            'mate_name': str(mate_name or "Squid")[:32],
            'at': stamp,
        }
        self.egg = {
            'egg_id': mating_id,
            'state': EGG_INCUBATING,
            'laid_at': stamp,
            'x': float(x),
            'y': float(y),
        }
        return True

    def starve(self, squid, health_loss: float, starvation_hunger: float) -> bool:
        """Apply one tick of starvation to a parent. True if it just died.

        Only a parent starves. Its hunger has been rising by the ordinary rule
        because it no longer eats; once that hunger is past the starvation
        line, the tank's own health loss for this tick is applied.
        """
        if self.stage != STAGE_PARENT or squid is None:
            return False
        if float(getattr(squid, 'hunger', 0.0)) >= float(starvation_hunger):
            squid.health = max(0.0, float(getattr(squid, 'health', 100.0))
                               - max(0.0, float(health_loss)))
        if float(getattr(squid, 'health', 100.0)) <= 0.0:
            return self.die()
        return False

    def die(self) -> bool:
        """parent -> dead. True only once."""
        if self.stage != STAGE_PARENT:
            return False
        self.stage = STAGE_DEAD
        return True

    def begin_hatching(self) -> bool:
        """The dead parent's egg starts to hatch. True only once."""
        if self.stage != STAGE_DEAD or self.egg is None:
            return False
        if self.egg.get('state') != EGG_INCUBATING:
            return False
        self.egg['state'] = EGG_HATCHING
        return True

    # -- persistence ----------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage': self.stage,
            'reproduction': dict(self.reproduction) if self.reproduction else None,
            'egg': dict(self.egg) if self.egg else None,
        }

    @classmethod
    def from_dict(cls, data: Any) -> 'Lifecycle':
        """Rebuild from a save. Anything unrecognisable reads as a living squid.

        Old saves have no lifecycle at all, and that is exactly a squid that
        has never reproduced.
        """
        lifecycle = cls()
        if not isinstance(data, dict):
            return lifecycle
        stage = data.get('stage')
        reproduction = data.get('reproduction')
        egg = data.get('egg')
        if stage not in (STAGE_PARENT, STAGE_DEAD):
            return lifecycle
        if not isinstance(reproduction, dict) or not is_valid_mating_id(
                reproduction.get('mating_id')):
            return lifecycle
        lifecycle.stage = stage
        lifecycle.reproduction = {
            'mating_id': reproduction['mating_id'],
            'mate_uuid': str(reproduction.get('mate_uuid', '')),
            'mate_name': str(reproduction.get('mate_name', 'Squid'))[:32],
            'at': _number(reproduction.get('at')),
        }
        if isinstance(egg, dict) and egg.get('state') in EGG_STATES:
            lifecycle.egg = {
                'egg_id': str(egg.get('egg_id') or reproduction['mating_id']),
                'state': egg['state'],
                'laid_at': _number(egg.get('laid_at')),
                'x': _number(egg.get('x')),
                'y': _number(egg.get('y')),
            }
        return lifecycle


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = ['Lifecycle', 'is_valid_mating_id', 'DEFAULT_CONFIG',
           'STAGE_LIVING', 'STAGE_PARENT', 'STAGE_DEAD', 'STAGES',
           'EGG_INCUBATING', 'EGG_HATCHING', 'EGG_STATES']
