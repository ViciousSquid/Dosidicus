#!/usr/bin/env python3
"""Add the life timeline to a save made before the game wrote one.

    python tools/add_timeline.py SAVE.zip [MORE.zip ...]      writes SAVE.timeline.zip
    python tools/add_timeline.py --in-place SAVE.zip

The Laboratory (extras/Laboratory.html) reads a squid's life from the
timeline.json in its save. The game writes that from 3.5 on; this adds it to
an older save, from what that save already records (src/life_timeline.py).
Nothing else in the save is changed.
"""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def add_timeline(source, target=None):
    """Write `source` with a timeline.json built from its own contents."""
    from src.life_timeline import build
    source = Path(source)
    target = Path(target) if target else source.with_name(source.stem + '.timeline.zip')
    with zipfile.ZipFile(source) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    sections = {}
    for name, data in entries.items():
        if name.endswith('.json') and name != 'timeline.json':
            try:
                sections[name[:-5]] = json.loads(data)
            except ValueError:
                pass
    entries['timeline.json'] = json.dumps(build(sections), indent=1).encode('utf-8')
    temporary = target.with_name(target.name + '.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    temporary.replace(target)
    return target


if __name__ == '__main__':
    arguments = [a for a in sys.argv[1:] if a != '--in-place']
    if not arguments:
        print(__doc__)
        sys.exit(2)
    for save in arguments:
        made = add_timeline(save, save if '--in-place' in sys.argv[1:] else None)
        print(f'{save} -> {made}')
