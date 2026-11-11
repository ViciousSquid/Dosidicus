"""Three save slots, each a tank with its own squid.

A squid's save is still what it always was: a zip named after the squid,
`{uuid}.zip`, with its autosave `{uuid}_autosave.zip` beside it, flat in the
saves folder. A slot is only a line in `saves/slots.json` saying which squid
is in it, and which slot is being played:

    {"active": 2, "slots": {"1": "<uuid>", "2": "<uuid>", "3": null}}

Nothing here is cached: the file and the folder are read each time, because
the game has more than one SaveManager looking at the same folder.

The index heals itself against the folder. A slot whose squid has no save
left is empty. A squid's save that is in no slot - one from before there
were slots, or a hatchling from the Squid Breeder dropped into the folder -
is given a free slot. With every slot taken it is left where it is, in no
slot, and never deleted.

Qt-free: the phone could use it as it is.
"""
import json
import os
import re
import zipfile
from typing import Dict, List, Optional

SLOTS = 3
INDEX = 'slots.json'
#: Names the game used before saves were named after their squid.
LEGACY = frozenset({'autosave.zip', 'autosave_backup.zip', 'save_data.zip'})
_UUID = re.compile(r'^[0-9a-f]{8}([-_][0-9a-f]{4}){3}[-_][0-9a-f]{12}$', re.I)
_LEFTOVERS = ('.backup', '.old', '.tmp')


def normal(squid_uuid) -> str:
    """One spelling for a squid's id: lower case, with hyphens."""
    return str(squid_uuid or '').strip().lower().replace('_', '-')


def squid_of(path) -> Optional[str]:
    """Whose save a file is: by its name, else by what it holds."""
    stem = os.path.basename(str(path))
    if stem.lower().endswith('.zip'):
        stem = stem[:-4]
    if stem.endswith('_autosave'):
        stem = stem[:-len('_autosave')]
    if _UUID.match(stem):
        return normal(stem)
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if 'uuid.txt' in names:
                raw = archive.read('uuid.txt').decode('utf-8', 'replace').strip()
                found = normal(raw.split('SquidSignature')[-1])
                if _UUID.match(found):
                    return found
            if 'game_state.json' in names:
                squid = (json.loads(archive.read('game_state.json')).get('squid') or {})
                found = normal(squid.get('uuid'))
                if _UUID.match(found):
                    return found
    except (OSError, ValueError, zipfile.BadZipFile, KeyError):
        pass
    return None


class SaveSlots:
    def __init__(self, directory='saves'):
        self.directory = str(directory)

    # ------------------------------------------------------------- the index
    @property
    def index_path(self) -> str:
        return os.path.join(self.directory, INDEX)

    def _read(self) -> Dict:
        data = {}
        try:
            with open(self.index_path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            pass
        slots = data.get('slots') if isinstance(data, dict) else None
        slots = slots if isinstance(slots, dict) else {}
        clean, seen = {}, set()
        for number in range(1, SLOTS + 1):
            squid = normal(slots.get(str(number))) or None
            if squid in seen or (squid and not _UUID.match(squid)):
                squid = None                    # one squid, one slot
            if squid:
                seen.add(squid)
            clean[number] = squid
        try:
            active = int(data.get('active', 1))
        except (TypeError, ValueError, AttributeError):
            active = 1
        return {'active': active if 1 <= active <= SLOTS else 1, 'slots': clean}

    def _write(self, state: Dict) -> None:
        os.makedirs(self.directory, exist_ok=True)
        payload = {'active': state['active'],
                   'slots': {str(n): state['slots'][n] for n in range(1, SLOTS + 1)}}
        temporary = self.index_path + '.tmp'
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=1)
        os.replace(temporary, self.index_path)

    # ------------------------------------------------------------ the folder
    def squids_on_disk(self) -> Dict[str, List[str]]:
        """{squid: its save files, newest first}."""
        found: Dict[str, List[str]] = {}
        try:
            names = os.listdir(self.directory)
        except OSError:
            return found
        for name in names:
            if not name.lower().endswith('.zip') or name in LEGACY:
                continue
            path = os.path.join(self.directory, name)
            squid = squid_of(path)
            if squid:
                found.setdefault(squid, []).append(path)
        for paths in found.values():
            paths.sort(key=_modified, reverse=True)
        return found

    def refresh(self) -> Dict:
        """The index, healed against the folder. Returns
        {'active', 'slots': {n: squid or None}, 'unslotted': [squid, ...]}."""
        state = self._read()
        before = json.dumps(state, sort_keys=True)
        disk = self.squids_on_disk()
        for number, squid in state['slots'].items():
            if squid and squid not in disk:
                state['slots'][number] = None
        placed = {squid for squid in state['slots'].values() if squid}
        waiting = sorted((squid for squid in disk if squid not in placed),
                         key=lambda squid: _modified(disk[squid][0]), reverse=True)
        for number in range(1, SLOTS + 1):
            if state['slots'][number] is None and waiting:
                state['slots'][number] = waiting.pop(0)
        if json.dumps(state, sort_keys=True) != before or not os.path.exists(self.index_path):
            try:
                self._write(state)
            except OSError:
                pass
        state['unslotted'] = waiting
        return state

    # --------------------------------------------------------------- reading
    @property
    def active(self) -> int:
        return self._read()['active']

    def squid_in(self, slot: int) -> Optional[str]:
        return self.refresh()['slots'].get(int(slot))

    def slot_of(self, squid_uuid) -> Optional[int]:
        squid = normal(squid_uuid)
        for number, held in self.refresh()['slots'].items():
            if held and held == squid:
                return number
        return None

    def path_for(self, slot: Optional[int] = None) -> Optional[str]:
        """The newest save of the squid in a slot (the active one by default)."""
        state = self.refresh()
        squid = state['slots'].get(int(slot) if slot is not None else state['active'])
        paths = self.squids_on_disk().get(squid) if squid else None
        return paths[0] if paths else None

    def describe(self) -> List[Dict]:
        """One entry per slot, for the chooser: empty, or who is in it."""
        state = self.refresh()
        disk = self.squids_on_disk()
        entries = []
        for number in range(1, SLOTS + 1):
            squid = state['slots'][number]
            entry = {'slot': number, 'active': number == state['active'], 'empty': squid is None,
                     'uuid': squid}
            if squid:
                entry.update(_summary(disk[squid][0]))
            entries.append(entry)
        return entries

    # --------------------------------------------------------------- writing
    def set_active(self, slot: int) -> None:
        slot = int(slot)
        if not 1 <= slot <= SLOTS:
            raise ValueError(f'there is no slot {slot}')
        state = self._read()
        state['active'] = slot
        self._write(state)

    def choose_startup_slot(self) -> int:
        """Once, as the game starts: the slot last played if a squid is in
        it, else the one saved most recently, else the slot last played."""
        state = self.refresh()
        if state['slots'][state['active']] is None:
            disk = self.squids_on_disk()
            taken = [n for n in range(1, SLOTS + 1) if state['slots'][n]]
            if taken:
                newest = max(taken, key=lambda n: _modified(disk[state['slots'][n]][0]))
                self.set_active(newest)
                return newest
        return state['active']

    def record_save(self, squid_uuid) -> Optional[int]:
        """A squid has just been saved: see that it is in a slot.

        One already in a slot stays there. A new one takes the active slot
        when that slot's squid is gone (it died, hatched an heir, or the
        player began again there), else a free slot. Either way the slot it
        is in becomes the one being played: the squid the game has just
        saved is the squid the game is playing.
        """
        squid = normal(squid_uuid)
        if not _UUID.match(squid):
            return None
        state = self._read()
        before = json.dumps(state, sort_keys=True)
        found = next((number for number, held in state['slots'].items() if held == squid), None)
        if found is None:
            disk = self.squids_on_disk()
            active = state['active']
            order = [active] + [n for n in range(1, SLOTS + 1) if n != active]
            for number in order:
                held = state['slots'][number]
                if held is None or held not in disk:
                    state['slots'][number] = squid
                    found = number
                    break
        if found is not None:
            state['active'] = found
        if json.dumps(state, sort_keys=True) != before or not os.path.exists(self.index_path):
            self._write(state)
        return found

    def delete(self, slot: int) -> int:
        """Delete the squid in a slot: every save it has. Returns how many
        files went. The slot is then empty."""
        state = self.refresh()
        squid = state['slots'].get(int(slot))
        if not squid:
            return 0
        removed = 0
        for path in self.squids_on_disk().get(squid, []):
            for candidate in [path] + [path + ending for ending in _LEFTOVERS]:
                try:
                    os.remove(candidate)
                    removed += 1
                except OSError:
                    pass
        state = self._read()
        state['slots'][int(slot)] = None
        self._write(state)
        return removed


def _modified(path) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _summary(path) -> Dict:
    """What the chooser says about a save. Never raises."""
    summary = {'path': path, 'saved_at': _modified(path), 'name': '', 'personality': '',
               'stage': 'living', 'age_seconds': 0.0}
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            game = json.loads(archive.read('game_state.json')) if 'game_state.json' in names else {}
            squid = game.get('squid') or {}
            summary['name'] = str(squid.get('name') or '')
            summary['personality'] = str(squid.get('personality') or '')
            summary['stage'] = str((game.get('lifecycle') or {}).get('stage') or 'living')
            if 'statistics.json' in names:
                statistics = json.loads(archive.read('statistics.json')) or {}
                summary['age_seconds'] = float(statistics.get('total_age_seconds') or 0.0)
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, TypeError, AttributeError):
        pass
    return summary


__all__ = ['SLOTS', 'SaveSlots', 'normal', 'squid_of']
