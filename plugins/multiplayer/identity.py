# File: identity.py
"""Who a squid is, as distinct from where its packets come from.

`node_id` is generated fresh every time the multiplayer plugin sets up
(`squid_<uuid4 hex[:6]>`), so it answers "which socket" and cannot answer
"which squid". Recognising an individual across sessions needs something that
outlives the process, and the game already has one: `Squid.uuid` is created at
birth, written into the save file, and restored from it on load.

So this module does not invent an identity scheme. It reads the one that is
already persisted and gives it a shape that can cross the network.
"""

import re
import uuid as _uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

#: Bumped when the meaning of a field changes, so two instances running
#: different versions can decline to interpret each other's payloads.
ENCOUNTER_PROTOCOL_VERSION = 1

#: A uuid as text and nothing else. Peer identity is used to build memory keys
#: and to look up relationship history, so a malformed one from the network
#: must never reach either.
_UUID_RE = re.compile(r'^[0-9a-fA-F-]{32,36}$')

_MAX_NAME = 32


def _clean_name(value: Any) -> str:
    """A display name safe to put in a memory the player will read."""
    text = str(value or "").strip()
    text = re.sub(r'[^\w \-\'.]', '', text)
    return text[:_MAX_NAME] or "Squid"


@dataclass(frozen=True)
class SquidIdentity:
    """A squid, recognisable across sessions and across tanks."""

    uuid: str
    name: str = "Squid"
    personality: str = "unknown"
    protocol: int = ENCOUNTER_PROTOCOL_VERSION

    # -- construction ---------------------------------------------------
    @classmethod
    def from_squid(cls, squid) -> Optional['SquidIdentity']:
        """Read the identity the save file already persists."""
        if squid is None:
            return None
        raw = getattr(squid, 'uuid', None)
        if raw is None:
            return None
        personality = getattr(squid, 'personality', None)
        return cls(
            uuid=str(raw),
            name=_clean_name(getattr(squid, 'name', None)),
            personality=str(getattr(personality, 'value', personality) or "unknown"),
        )

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> Optional['SquidIdentity']:
        """Build an identity from a network payload, or None if it is junk.

        Everything here arrives from another machine, so nothing is trusted:
        an unparseable uuid is rejected outright rather than being allowed to
        become a memory key, and the name is stripped of anything that is not
        a plain character.
        """
        if not isinstance(payload, dict):
            return None
        raw = payload.get('uuid')
        if not isinstance(raw, str) or not _UUID_RE.match(raw.strip()):
            return None
        try:
            canonical = str(_uuid.UUID(raw.strip()))
        except (ValueError, AttributeError, TypeError):
            return None
        try:
            protocol = int(payload.get('protocol', ENCOUNTER_PROTOCOL_VERSION))
        except (TypeError, ValueError):
            return None
        return cls(
            uuid=canonical,
            name=_clean_name(payload.get('name')),
            personality=_clean_name(payload.get('personality')).lower() or "unknown",
            protocol=protocol,
        )

    # -- use ------------------------------------------------------------
    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def memory_key(self) -> str:
        """The key an experience with this individual is filed under.

        MemoryManager identifies a memory by (category, key), so this is what
        makes "I met B" and "I met C" two experiences instead of one record
        whose importance keeps going up.
        """
        return f"peer:{self.uuid}"

    @property
    def short_id(self) -> str:
        return self.uuid[:8]

    def is_compatible(self) -> bool:
        return self.protocol == ENCOUNTER_PROTOCOL_VERSION

    def __str__(self) -> str:
        return f"{self.name} ({self.short_id})"


def memory_key_for(peer_uuid: str) -> str:
    """Memory key for a peer uuid, without needing the whole identity."""
    return f"peer:{str(peer_uuid)}"
