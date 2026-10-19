"""Export / import a squid as a .zip, matching the desktop layout.

The archive contains the same files the desktop app produces so squids can be
shared through the Squid-Exchange ecosystem:

    game_state.json    - desktop-shaped pet data
    mobile_state.json  - the authoritative mobile save (full fidelity)
    brain_state.json   - desktop-shaped brain (weights_list, neuron_positions...)
    statistics.json    - lifetime stats (identical field names to desktop)
    ShortTerm.json     - short-term memories
    LongTerm.json      - long-term memories
    custom_brain.json  - null (the full network is in brain_state.json)
    achievements.json  - achievement progress
    uuid.txt           - "SquidSignature\\t<uuid>"

Import reads mobile_state.json for an exact round-trip, and
falls back to a best-effort reconstruction from a desktop archive (squid stats,
brain weights/positions and memories).
"""

from __future__ import annotations

import gzip
import io
import json
import zipfile
from datetime import datetime

from .simulation import Simulation
from .squid import Squid
from .personality import Personality
from .memory import MemoryManager


# --------------------------------------------------------------------- export
def _brain_state_desktop(brain):
    """Desktop-shaped brain_state.json from our NeuralBrain."""
    from src.brain_io import desktop_brain_state
    return desktop_brain_state(brain.to_dict())


def _memories_desktop(mem_list):
    out = []
    for m in mem_list:
        out.append({
            "timestamp": m.get("wall", 0) or 0,
            "category": m.get("category"),
            "key": m.get("key"),
            "value": m.get("value"),
            "importance": m.get("importance", 1.0),
            "related_neurons": m.get("related_neurons", []),
            "access_count": m.get("access_count", 1),
        })
    return out


def export_squid(sim: Simulation, path: str):
    """Write ``sim`` to a shareable .zip at ``path``."""
    squid = sim.squid
    from copy import deepcopy
    from src.save_archive import write_save_archive
    files = deepcopy(getattr(sim, '_desktop_sections', {}))
    previous_game = files.get('game_state') or {}
    pet = {key: value for key, value in squid.to_dict().items() if key not in ('brain', 'memory', 'stats')}
    pet.update({name: getattr(squid, name) for name in squid.CORE_STATS})
    pet.update(squid_x=squid.x, squid_y=squid.y)
    files.update({
        'game_state': dict(previous_game,
            squid=dict(previous_game.get('squid', {}), **pet),
            tamagotchi_logic=previous_game.get('tamagotchi_logic', {}),
            decorations=previous_game.get('decorations', [])),
        'mobile_state': sim.to_dict(),
        'brain_state': _brain_state_desktop(squid.brain),
        'statistics': sim.stats.to_dict(),
        'ShortTerm': _memories_desktop(squid.memory.short_term),
        'LongTerm': _memories_desktop(squid.memory.long_term),
        'custom_brain': files.get('custom_brain'),
        'achievements': sim.achievements.to_dict(),
    })
    write_save_archive(path, files, squid.uuid)
    return path


# -------------------------------------------------- snapshots (local P2P)
# A snapshot is the full mobile save, JSON-encoded and gzipped, for sending a
# squid over a short-range link (Nearby Connections). It stays small enough for
# a single Nearby BYTES payload (~32 KB) for all but the most elaborate brains.
SNAPSHOT_MAX_BYTES = 32000


def snapshot_bytes(sim) -> bytes:
    raw = json.dumps(sim.to_dict(), separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=9)


def snapshot_dict(data: bytes) -> dict:
    return json.loads(gzip.decompress(data).decode("utf-8"))


def sim_from_snapshot(data: bytes, tank_size=(900, 500)) -> Simulation:
    sim = Simulation.from_dict(snapshot_dict(data))
    sim.tank_size = tank_size
    sim.squid.tank_size = tank_size
    return sim


# --------------------------------------------------------------------- import
def _read_json(z, name, default=None):
    try:
        if z.getinfo(name).file_size > 16 * 1024 * 1024:
            raise ValueError('Archive member exceeds 16 MiB: ' + name)
        return json.loads(z.read(name).decode("utf-8"))
    except KeyError:
        return default


def import_squid(path: str, tank_size=(900, 500)) -> Simulation:
    """Load a squid .zip. Mobile archives round-trip exactly; desktop archives
    are reconstructed best-effort."""
    from copy import deepcopy
    from src.brain_io import read_brain_file
    from .brain import NeuralBrain
    from .statistics import Statistics
    from .achievements import AchievementManager
    with zipfile.ZipFile(path, 'r') as archive:
        sections = {name[:-5]: _read_json(archive, name)
                    for name in archive.namelist() if name.endswith('.json') and '/' not in name}
    game = sections.get('game_state') or {}
    mobile = sections.get('mobile_state')
    if mobile is None and 'version' in game and 'tank_size' in game:
        mobile = game  # pre-3.1 mobile export
    sim = Simulation.from_dict(mobile) if mobile is not None else Simulation(tank_size=tank_size)
    sim.tank_size = sim.squid.tank_size = tank_size
    squid = sim.squid
    pet = game.get('squid') or {}
    squid.personality = Personality.from_value(pet.get('personality', squid.personality.value))
    for name in squid.CORE_STATS:
        if name in pet:
            setattr(squid, name, float(pet[name]))
    for name in ('uuid', 'name', 'is_sick', 'is_sleeping', 'is_dead', 'age_seconds', 'direction'):
        if name in pet:
            setattr(squid, name, pet[name])
    squid.x = pet.get('squid_x', pet.get('x', squid.x))
    squid.y = pet.get('squid_y', pet.get('y', squid.y))
    if pet.get('tint_color'):
        squid.color_tint = tuple(channel / 255.0 for channel in pet['tint_color'])
    if sections.get('brain_state') or (sections.get('custom_brain') or {}).get('is_custom_brain'):
        payload = read_brain_file(path)
        payload.update(personality=squid.personality.value, sim_time=squid.brain.sim_time)
        squid.brain = NeuralBrain.from_dict(payload)
    elif mobile is None:
        raise ValueError('Save contains no brain')
    # Preserve exact mobile memory timing if the desktop view has not changed.
    for key, attribute in (('ShortTerm', 'short_term'), ('LongTerm', 'long_term')):
        memories = sections.get(key)
        if memories is not None and memories != _memories_desktop(getattr(squid.memory, attribute)):
            converted = []
            for memory in memories:
                item = deepcopy(memory)
                item['wall'] = item.get('timestamp', 0)
                item['timestamp'] = squid.brain.sim_time
                converted.append(item)
            setattr(squid.memory, attribute, converted)
    if 'statistics' in sections:
        sim.stats = Statistics.from_dict(sections['statistics'])
    if 'achievements' in sections:
        sim.achievements = AchievementManager.from_dict(sections['achievements'])
    sim._desktop_sections = {key: value for key, value in sections.items() if key != 'mobile_state'}
    return sim
