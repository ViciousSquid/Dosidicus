#!/usr/bin/env python3
"""Version, assemble and checksum the same immutable source on every runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?')
RUNTIME = ('images', 'plugins', 'src', 'translations', 'custom_brains',
           'example_squids', 'config.ini', 'version', 'LICENSE', 'README.md',
           'release-info.json')


def validate_version(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError('Use MAJOR.MINOR.PATCH, optionally followed by -prerelease')
    major, minor, patch = map(int, match.group(1, 2, 3))
    code = major * 10000 + minor * 100 + patch
    if minor > 99 or patch > 99 or not 0 < code <= 2100000000:
        raise ValueError('Android requires minor/patch <= 99 and a positive version code <= 2100000000')
    return code


def set_version(root, version):
    code = validate_version(version)
    p = root / 'version'
    p.write_text(re.sub(r'^dosidicus:.*$', f'dosidicus: {version}', p.read_text(), flags=re.M))
    p = root / 'android/buildozer.spec'
    s = re.sub(r'^version = .*$', f'version = {version}', p.read_text(), flags=re.M)
    p.write_text(re.sub(r'^android.numeric_version = .*$', f'android.numeric_version = {code}', s, flags=re.M))
    p = root / 'android/dosidicus_mobile/__init__.py'
    p.write_text(re.sub(r'^__version__ = .*$', f'__version__ = "{version}-mobile"', p.read_text(), flags=re.M))
    (root / 'release-info.json').write_text(json.dumps({
        'version': version, 'commit': os.environ.get('GITHUB_SHA', ''),
        'run': os.environ.get('GITHUB_RUN_ID', ''),
    }, indent=2) + '\n')


def copy_runtime(root, target):
    """Ship runtime assets, never .git credentials, build caches or other APKs."""
    target.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME:
        source = root / name
        if source.is_dir():
            shutil.copytree(source, target / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.log', '*.tmp'))
        elif source.is_file():
            shutil.copy2(source, target / name)
    for name in ('images', 'plugins', 'src', 'config.ini', 'version'):
        if not (target / name).exists():
            raise ValueError(f'Missing runtime data: {name}')


def collect_artifacts(source, target, version):
    validate_version(version)
    expected = {
        'Dosidicus-windows.zip': 'windows-x64.zip',
        'Dosidicus-windows-arm64.zip': 'windows-arm64.zip',
        'Dosidicus-macos-arm64.zip': 'macos-arm64.zip',
        'Dosidicus-macos-arm64.dmg': 'macos-arm64.dmg',
        'Dosidicus-macos-arm64-debug.zip': 'macos-arm64-debug.zip',
        'Dosidicus-macos-x64.zip': 'macos-x64.zip',
        'Dosidicus-macos-x64.dmg': 'macos-x64.dmg',
        'Dosidicus-macos-x64-debug.zip': 'macos-x64-debug.zip',
        'Dosidicus-linux.tar.gz': 'linux-x64.tar.gz',
        f'dosidicus-{version}-arm64-release.apk': 'android-arm64.apk',
    }
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        raise ValueError('Release asset directory must be empty')
    for original, suffix in expected.items():
        matches = list(source.rglob(original))
        if len(matches) != 1 or matches[0].stat().st_size == 0:
            raise ValueError(f'Expected exactly one nonempty {original}, got {len(matches)}')
        shutil.copy2(matches[0], target / f'Dosidicus-{version}-{suffix}')
    metadata = {'version': version, 'commit': os.environ.get('GITHUB_SHA', ''),
                'run': os.environ.get('GITHUB_RUN_ID', ''),
                'artifacts': sorted(p.name for p in target.iterdir())}
    (target / 'release-info.json').write_text(json.dumps(metadata, indent=2) + '\n')
    hashes = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
              for p in sorted(target.iterdir())]
    (target / 'SHA256SUMS').write_text(''.join(hashes))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('version', 'runtime', 'collect'))
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--version')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    if args.action == 'version':
        set_version(args.root, args.version)
    elif args.action == 'runtime':
        copy_runtime(args.root, args.target)
    else:
        collect_artifacts(args.source, args.target, args.version)


if __name__ == '__main__':
    main()

