"""One DMG for every Mac, made by the Nuitka build itself.

The build makes the game for Apple Silicon and for Intel. tools/
merge_macos_universal.py joins the two app bundles into one universal app:
compiled files joined with lipo, everything else copied once. lipo exists
only on a Mac, so here it is played by a small stand-in that knows the two
things asked of it; the real one is exercised by the workflow, which then
starts the result on both kinds of Mac.
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.merge_macos_universal import MergeError, is_macho, merge, summary   # noqa: E402

THIN = b'\xcf\xfa\xed\xfe'          # one architecture, 64-bit
FAT = b'\xca\xfe\xba\xbe'           # several

# A stand-in for lipo: a "compiled file" here is its magic, then the names of
# the architectures it carries, one per line.
LIPO = r'''#!/usr/bin/env python3
import sys
FAT = b'\xca\xfe\xba\xbe'
def archs(path):
    return open(path, 'rb').read()[4:].decode().split()
args = sys.argv[1:]
if args[0] == '-archs':
    print(' '.join(archs(args[1])))
elif args[0] == '-create':
    out = args[args.index('-output') + 1]
    parts = [a for a in args[1:args.index('-output')]]
    joined = []
    for part in parts:
        for arch in archs(part):
            if arch in joined:
                sys.exit('same architecture twice')
            joined.append(arch)
    open(out, 'wb').write(FAT + '\n'.join(joined).encode())
else:
    sys.exit(1)
'''


def compiled(path, *architectures):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((THIN if len(architectures) == 1 else FAT)
                     + '\n'.join(architectures).encode())
    path.chmod(0o755)


def bundle(root, arch, extra=None):
    app = root / 'Dosidicus.app'
    macos = app / 'Contents' / 'MacOS'
    compiled(macos / 'Dosidicus', arch)
    compiled(macos / 'PyQt5' / 'qt-plugins' / 'platforms' / 'libqcocoa.dylib', arch)
    compiled(macos / 'QtCore', arch)
    (macos / 'libpython.dylib').symlink_to('QtCore')
    (macos / 'images').mkdir()
    (macos / 'images' / 'squid.png').write_bytes(b'the same picture')
    (macos / 'config.ini').write_text('[General]\n')
    (app / 'Contents' / 'Info.plist').write_text('<plist/>')
    for name, content in (extra or {}).items():
        if isinstance(content, tuple):
            compiled(macos / name, *content)
        else:
            (macos / name).parent.mkdir(parents=True, exist_ok=True)
            (macos / name).write_bytes(content)
    return app


@pytest.fixture
def lipo(tmp_path):
    path = tmp_path / 'lipo'
    path.write_text(LIPO)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def carried(path):
    return path.read_bytes()[4:].decode().split()


def test_compiled_code_is_told_from_everything_else(tmp_path):
    compiled(tmp_path / 'thin', 'arm64')
    compiled(tmp_path / 'fat', 'arm64', 'x86_64')
    (tmp_path / 'picture.png').write_bytes(b'\x89PNG....')
    (tmp_path / 'empty').write_bytes(b'')
    assert is_macho(tmp_path / 'thin') and is_macho(tmp_path / 'fat')
    assert not is_macho(tmp_path / 'picture.png') and not is_macho(tmp_path / 'empty')
    assert not is_macho(tmp_path / 'missing')


def test_two_builds_become_one_app_for_every_mac(tmp_path, lipo):
    arm = bundle(tmp_path / 'arm', 'arm64')
    intel = bundle(tmp_path / 'intel', 'x86_64')
    out = tmp_path / 'universal' / 'Dosidicus.app'
    out.parent.mkdir()
    report = merge(arm, intel, out, lipo)
    macos = out / 'Contents' / 'MacOS'
    # Every compiled file now carries both.
    for name in ('Dosidicus', 'QtCore', 'PyQt5/qt-plugins/platforms/libqcocoa.dylib'):
        assert carried(macos / name) == ['arm64', 'x86_64'], name
    assert sorted(report['joined']) == sorted(
        f'Contents/MacOS/{name}' for name in
        ('Dosidicus', 'QtCore', 'PyQt5/qt-plugins/platforms/libqcocoa.dylib'))
    assert report['executable'] == ['arm64', 'x86_64']
    # It can still be run, links are still links, and the rest is there once.
    assert os.access(macos / 'Dosidicus', os.X_OK)
    assert (macos / 'libpython.dylib').is_symlink()
    assert os.readlink(macos / 'libpython.dylib') == 'QtCore'
    assert (macos / 'images' / 'squid.png').read_bytes() == b'the same picture'
    assert report['only_arm64'] == report['only_x86_64'] == []
    assert report['kept_arm64_where_they_differ'] == []
    # The two builds it was made from are untouched.
    assert carried(arm / 'Contents' / 'MacOS' / 'Dosidicus') == ['arm64']
    assert carried(intel / 'Contents' / 'MacOS' / 'Dosidicus') == ['x86_64']
    assert 'Joined 3 compiled files' in summary(report)


def test_what_only_one_build_has_is_kept_and_said(tmp_path, lipo):
    arm = bundle(tmp_path / 'arm', 'arm64', {'numpy/libaccelerate.dylib': ('arm64',),
                                             'src/__pycache__/ui.pyc': b'compiled on arm'})
    intel = bundle(tmp_path / 'intel', 'x86_64', {'numpy/libgfortran.dylib': ('x86_64',),
                                                  'src/__pycache__/ui.pyc': b'compiled on intel',
                                                  'numpy/link': b''})
    (intel / 'Contents' / 'MacOS' / 'numpy' / 'link').unlink()
    (intel / 'Contents' / 'MacOS' / 'numpy' / 'link').symlink_to('libgfortran.dylib')
    out = tmp_path / 'Dosidicus.app'
    report = merge(arm, intel, out, lipo)
    macos = out / 'Contents' / 'MacOS'
    assert carried(macos / 'numpy' / 'libaccelerate.dylib') == ['arm64']
    assert carried(macos / 'numpy' / 'libgfortran.dylib') == ['x86_64']
    assert os.readlink(macos / 'numpy' / 'link') == 'libgfortran.dylib'
    assert report['only_arm64'] == ['Contents/MacOS/numpy/libaccelerate.dylib']
    assert sorted(report['only_x86_64']) == ['Contents/MacOS/numpy/libgfortran.dylib',
                                             'Contents/MacOS/numpy/link']
    # Not compiled code and different: the Apple Silicon one, and it is said.
    assert (macos / 'src' / '__pycache__' / 'ui.pyc').read_bytes() == b'compiled on arm'
    assert report['kept_arm64_where_they_differ'] == ['Contents/MacOS/src/__pycache__/ui.pyc']
    text = summary(report)
    assert 'Only in the Intel build (2)' in text and 'Apple Silicon one kept' in text


def test_a_file_that_already_carries_both_is_left_alone(tmp_path, lipo):
    arm = bundle(tmp_path / 'arm', 'arm64', {'libboth.dylib': ('arm64', 'x86_64'),
                                             'libneeds.dylib': ('arm64',)})
    intel = bundle(tmp_path / 'intel', 'x86_64', {'libboth.dylib': ('x86_64',),
                                                  'libneeds.dylib': ('arm64', 'x86_64')})
    out = tmp_path / 'Dosidicus.app'
    report = merge(arm, intel, out, lipo)
    macos = out / 'Contents' / 'MacOS'
    assert carried(macos / 'libboth.dylib') == ['arm64', 'x86_64']
    assert carried(macos / 'libneeds.dylib') == ['arm64', 'x86_64']
    assert sorted(report['already_universal']) == ['Contents/MacOS/libboth.dylib',
                                                   'Contents/MacOS/libneeds.dylib']


def test_it_stops_rather_than_make_an_app_that_cannot_work(tmp_path, lipo):
    # Two Apple Silicon builds are not a universal app.
    arm, also_arm = bundle(tmp_path / 'a', 'arm64'), bundle(tmp_path / 'b', 'arm64')
    (also_arm / 'Contents' / 'MacOS' / 'config.ini').write_text('[Other]\n')
    with pytest.raises(MergeError, match='not both'):
        merge(arm, also_arm, tmp_path / 'same.app', lipo)
    # Compiled in one, not in the other.
    intel = bundle(tmp_path / 'c', 'x86_64', {'QtGui': b'not compiled'})
    arm2 = bundle(tmp_path / 'd', 'arm64', {'QtGui': ('arm64',)})
    with pytest.raises(MergeError, match='compiled code in one'):
        merge(arm2, intel, tmp_path / 'mixed.app', lipo)
    # A link that points somewhere else.
    intel2 = bundle(tmp_path / 'e', 'x86_64')
    (intel2 / 'Contents' / 'MacOS' / 'libpython.dylib').unlink()
    (intel2 / 'Contents' / 'MacOS' / 'libpython.dylib').symlink_to('Dosidicus')
    with pytest.raises(MergeError, match='not the same link'):
        merge(bundle(tmp_path / 'f', 'arm64'), intel2, tmp_path / 'links.app', lipo)
    # Not app bundles, or somewhere already taken.
    with pytest.raises(MergeError, match='not an app bundle'):
        merge(tmp_path, intel2, tmp_path / 'x.app', lipo)
    taken = tmp_path / 'taken.app'
    taken.mkdir()
    with pytest.raises(MergeError, match='already exists'):
        merge(bundle(tmp_path / 'g', 'arm64'), bundle(tmp_path / 'h', 'x86_64'), taken, lipo)


def test_the_nuitka_build_makes_the_universal_dmg_itself():
    import re
    text = (ROOT / '.github' / 'workflows' / 'build-nuitka.yml').read_text(encoding='utf-8')
    for needed in ('macos-universal:', 'macos-universal-intel:', 'needs: build',
                   'tools/merge_macos_universal.py', 'tools/build_macos_dmg.sh',
                   'Dosidicus-macos-universal.dmg', 'nuitka-macos-universal-dmg',
                   'codesign --deep --force --sign -', '-verify_arch x86_64 arm64'):
        assert needed in text, needed
    # It is started on both kinds of Mac before it is published.
    assert re.search(r'macos_smoke_test\.sh .* arm64', text)
    assert re.search(r'macos_smoke_test\.sh .* x86_64', text)
    assert text.index('macos_smoke_test.sh "$MOUNT/Dosidicus.app" x86_64') \
        < text.index('name: nuitka-macos-universal-dmg')
    # And a release carries it.
    assert "'Dosidicus-macos-universal.dmg'" in (ROOT / 'tools' / 'release_support.py').read_text()
