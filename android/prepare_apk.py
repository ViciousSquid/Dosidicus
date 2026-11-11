#!/usr/bin/env python3
"""Stage the mobile app with the actual desktop engine for python-for-android."""
from pathlib import Path
import hashlib
import json
import shutil

SHARED_MODULES = (
    '__init__', 'brain_constants', 'propagation', 'plasticity', 'capability',
    'causal_learning', 'neural_provenance', 'consolidation', 'sleep_consolidation',
    'neurogenesis', 'learning', 'config_manager', 'personality', 'localisation',
    'portable_brain', 'neuron_binding', 'decision_engine', 'memory_manager', 'stdp', 'brain_clock', 'brain_io', 'save_archive',
    'vision_cone', 'lifecycle', 'fighting', 'social_learning', 'inheritance', 'throwing',
    'social_knowledge', 'action_discovery',
    # A squid's colour as its identity carries it, and its decision to go out.
    'tint', 'venturing',
    # The life in order, written into every save for the Laboratory pages.
    'life_timeline',
)

#: The Qt-free half of the desktop's multiplayer plugin. The first group is
#: a visit itself; the second is the network it travels on - the desktop's
#: own socket code and friend codes (dosidicus_mobile/engine/tank_link.py),
#: which is why a phone's squid and a computer's can visit each other.
MULTIPLAYER_MODULES = (
    '__init__', 'identity', 'remote_protocol', 'host_body',
    'visitor_mind', 'encounter', 'peer_ledger',
    'consent', 'friend_link', 'mp_constants', 'mp_network_node', 'network_utilities',
)


def prepare(destination=None):
    android = Path(__file__).resolve().parent
    root = android.parent
    target = Path(destination) if destination else android / '.buildozer' / 'mobile-source'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('dosidicus_mobile', 'assets'):
        shutil.copytree(android / name, target / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(android / 'main.py', target / 'main.py')
    shutil.copy2(root / 'config.ini', target / 'config.ini')
    (target / 'src').mkdir(exist_ok=True)
    manifest = {'engine': '3.1_LatestVersion', 'files': {}}
    for name in SHARED_MODULES:
        source = root / 'src' / (name + '.py')
        shutil.copy2(source, target / 'src' / source.name)
        manifest['files']['src/' + source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    multiplayer = MULTIPLAYER_MODULES
    for relative in ('plugins/achievements/__init__.py', 'plugins/achievements/achievements_data.py',
                     *(f'plugins/multiplayer/{name}.py' for name in multiplayer)):
        source = root / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest['files'][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.copytree(root / 'translations', target / 'translations', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for source in [target / 'main.py', *(target / 'dosidicus_mobile').rglob('*.py')]:
        manifest['files'][source.relative_to(target).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    (target / 'engine_manifest.json').write_text(json.dumps(manifest, indent=2))
    return target


if __name__ == '__main__':
    print(prepare())
