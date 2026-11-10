#!/usr/bin/env python3
"""Make one universal Dosidicus.app from the Apple Silicon and Intel ones.

The Nuitka build makes the game twice on macOS, once for each kind of Mac.
The two bundles hold the same files; what differs is the compiled code in
them - the game itself, Python, Qt, numpy. This puts each pair of compiled
files together into one file that carries both (Apple's `lipo`), and copies
everything else once, so one app and one DMG run on any Mac.

    python tools/merge_macos_universal.py ARM64.app X64.app OUTPUT.app

  * A compiled file (Mach-O) in both: joined with lipo. The same bytes in
    both, or one already carrying everything the other has: copied.
  * Anything else in both: the Apple Silicon one is kept. If the two differ
    it is listed in the report (compiled-Python caches and the like differ
    harmlessly; anything else there is worth a look).
  * A file in only one of them is kept as it is, and listed: it will only
    ever be used by that kind of Mac.
  * A link that points somewhere different in the two, or a file that is
    compiled code in one and not in the other, stops the merge.

The result is not signed: sign it afterwards (codesign --force --deep).
A report of what was done is printed and written to OUTPUT.app.merge.json.
"""
import argparse
import filecmp
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

#: The first four bytes of compiled code on a Mac: one architecture (32- and
#: 64-bit, either byte order) or several in one "fat" file.
MACHO = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
         b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}
WANTED = ('arm64', 'x86_64')


class MergeError(RuntimeError):
    """The two bundles cannot be made into one."""


def is_macho(path) -> bool:
    try:
        with open(path, 'rb') as handle:
            return handle.read(4) in MACHO
    except OSError:
        return False


def architectures(path, lipo='lipo'):
    """The architectures a compiled file carries, as lipo names them."""
    result = subprocess.run([lipo, '-archs', str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise MergeError(f'lipo could not read {path}: {result.stderr.strip()}')
    return set(result.stdout.split())


def _files(root: Path):
    """Every file and link under root, relative to it (directories are made
    as their contents are)."""
    found = {}
    for folder, folders, names in os.walk(root, followlinks=False):
        here = Path(folder)
        for name in list(folders):
            if (here / name).is_symlink():          # a link to a folder is a link
                found[(here / name).relative_to(root)] = here / name
                folders.remove(name)
        for name in names:
            found[(here / name).relative_to(root)] = here / name
    return found


def merge(arm_app, intel_app, output, lipo='lipo'):
    """Merge the two bundles into `output`. Returns the report."""
    arm_app, intel_app, output = Path(arm_app), Path(intel_app), Path(output)
    for app in (arm_app, intel_app):
        if not (app / 'Contents' / 'MacOS').is_dir():
            raise MergeError(f'{app} is not an app bundle')
    if output.exists():
        raise MergeError(f'{output} already exists')
    report = {'joined': [], 'same': 0, 'only_arm64': [], 'only_x86_64': [],
              'kept_arm64_where_they_differ': [], 'already_universal': []}
    shutil.copytree(arm_app, output, symlinks=True)
    arm, intel = _files(arm_app), _files(intel_app)

    for relative, source in sorted(intel.items()):
        target = output / relative
        name = str(relative)
        if relative not in arm:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                os.symlink(os.readlink(source), target)
            else:
                shutil.copy2(source, target)
            report['only_x86_64'].append(name)
            continue
        other = arm[relative]
        if source.is_symlink() or other.is_symlink():
            if not (source.is_symlink() and other.is_symlink()
                    and os.readlink(source) == os.readlink(other)):
                raise MergeError(f'{name} is not the same link in both bundles')
            report['same'] += 1
            continue
        compiled = (is_macho(other), is_macho(source))
        if compiled[0] != compiled[1]:
            raise MergeError(f'{name} is compiled code in one bundle and not in the other')
        if filecmp.cmp(other, source, shallow=False):
            report['same'] += 1
            continue
        if not compiled[0]:
            report['kept_arm64_where_they_differ'].append(name)
            continue
        have, more = architectures(other, lipo), architectures(source, lipo)
        if more <= have:                            # nothing new in the Intel one
            report['already_universal'].append(name)
            continue
        if have <= more:                            # the Intel one carries both
            shutil.copy2(source, target)
            report['already_universal'].append(name)
            continue
        if have & more:
            raise MergeError(f'{name}: {sorted(have)} and {sorted(more)} overlap; '
                             f'cannot be joined as they are')
        joined = target.with_name(target.name + '.universal')
        result = subprocess.run([lipo, '-create', str(other), str(source),
                                 '-output', str(joined)], capture_output=True, text=True)
        if result.returncode != 0:
            raise MergeError(f'lipo could not join {name}: {result.stderr.strip()}')
        shutil.copymode(other, joined)
        os.replace(joined, target)
        report['joined'].append(name)

    report['only_arm64'] = sorted(str(relative) for relative in arm if relative not in intel)
    # The game itself has to have come out carrying both.
    executable = output / 'Contents' / 'MacOS' / 'Dosidicus'
    if executable.exists():
        carried = architectures(executable, lipo)
        report['executable'] = sorted(carried)
        if not set(WANTED) <= carried:
            raise MergeError(f'the merged game carries {sorted(carried)}, not both of {WANTED}')
    return report


def summary(report) -> str:
    lines = [f"Joined {len(report['joined'])} compiled files into universal ones; "
             f"{report['same']} files were the same in both.",
             f"The game itself carries: {', '.join(report.get('executable', ['?']))}."]
    for key, title in (('already_universal', 'Already universal'),
                       ('only_arm64', 'Only in the Apple Silicon build'),
                       ('only_x86_64', 'Only in the Intel build'),
                       ('kept_arm64_where_they_differ',
                        'Not compiled code, different in the two (Apple Silicon one kept)')):
        names = report[key]
        if names:
            shown = ', '.join(names[:12]) + (f', and {len(names) - 12} more' if len(names) > 12 else '')
            lines.append(f'{title} ({len(names)}): {shown}')
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('arm64_app', type=Path)
    parser.add_argument('x64_app', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--lipo', default='lipo')
    args = parser.parse_args()
    try:
        made = merge(args.arm64_app, args.x64_app, args.output, args.lipo)
    except MergeError as problem:
        print(f'Cannot merge: {problem}', file=sys.stderr)
        sys.exit(1)
    Path(str(args.output) + '.merge.json').write_text(json.dumps(made, indent=1))
    print(summary(made))
