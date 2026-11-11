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
#: extras: the laboratory tools (Laboratory, Save Viewer, Squid Breeder),
#: which the game opens in a browser from View > Laboratory.
RUNTIME = ('images', 'plugins', 'src', 'translations', 'custom_brains',
           'example_squids', 'extras', 'config.ini', 'version', 'LICENSE', 'README.md',
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
    # A build made from a tree that has the laboratory tools must carry them
    # whole: the pages, and the scripts they load from beside themselves.
    if (root / 'extras').is_dir():
        for name in ('Laboratory.html', 'SaveViewer.html', 'SquidBreeder.html', 'README.md',
                     'vendor/lab.js', 'vendor/jszip.min.js', 'vendor/dosidicus_data.js'):
            if not (target / 'extras' / name).is_file():
                raise ValueError(f'Missing runtime data: extras/{name}')


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
        # One DMG for every Mac, joined from the two above by the build.
        'Dosidicus-macos-universal.dmg': 'macos-universal.dmg',
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


def plan_build(environ, root=Path('.'), tag_exists_elsewhere=None):
    """What a run of the build is, from how it was started.

    Returns {'version', 'tag', 'prerelease', 'release'} as the strings the
    workflow reads. Called by the release workflow, it builds at the version
    given and publishes nothing (that workflow does). Run by hand, it is a
    release: of the tag asked for, or of vVERSION-build.RUN - the game's
    version from the `version` file and this run's number, always a
    prerelease. A push just builds.
    """
    called_with = environ.get('CALLED_WITH_VERSION', '')
    if called_with:
        validate_version(called_with)
        return {'version': called_with, 'tag': '', 'prerelease': 'false', 'release': 'false'}
    if environ.get('BY_HAND') != 'true':
        return {'version': '', 'tag': '', 'prerelease': 'false', 'release': 'false'}
    tag = environ.get('REQUESTED_TAG', '').strip()
    if not tag:
        current = re.search(r'^dosidicus:\s*(\S+)', (root / 'version').read_text(), flags=re.M)
        if not current:
            raise ValueError('The version file has no "dosidicus:" line')
        base = '.'.join((current.group(1).split('-')[0].split('.') + ['0', '0'])[:3])
        tag = f"v{base}-build.{environ.get('GITHUB_RUN_NUMBER', '0')}"
    if not tag.startswith('v'):
        raise ValueError('Release tags must start with v')
    version = tag[1:]
    validate_version(version)
    if tag_exists_elsewhere and tag_exists_elsewhere(tag):
        raise ValueError(f'{tag} already exists at a different commit; choose another tag')
    if environ.get('HAS_KEYSTORE') != 'true':
        raise ValueError(
            'A release includes the Android APK, and it has to be signed. Set the '
            'repository secrets ANDROID_KEYSTORE_BASE64 and ANDROID_KEYSTORE_PASSWORD '
            '(Settings > Secrets and variables > Actions; docs/RELEASING.md) and run '
            'the build again. Nothing was built.')
    prerelease = environ.get('REQUESTED_PRERELEASE') == 'true' or '-' in version
    return {'version': version, 'tag': tag, 'prerelease': str(prerelease).lower(),
            'release': 'true'}


def _tag_is_elsewhere(tag):
    import subprocess
    found = subprocess.run(['git', 'rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}'],
                           capture_output=True, text=True)
    return found.returncode == 0 and found.stdout.strip() != os.environ.get('GITHUB_SHA', '')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('version', 'runtime', 'collect', 'plan'))
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--version')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    if args.action == 'version':
        set_version(args.root, args.version)
    elif args.action == 'runtime':
        copy_runtime(args.root, args.target)
    elif args.action == 'plan':
        try:
            planned = plan_build(os.environ, args.root, _tag_is_elsewhere)
        except ValueError as problem:
            raise SystemExit(f'::error::{problem}')
        for name, value in planned.items():
            print(f'{name}={value}')
    else:
        collect_artifacts(args.source, args.target, args.version)


if __name__ == '__main__':
    main()

