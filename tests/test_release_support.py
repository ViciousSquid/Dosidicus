"""Release inputs, version consistency, artifact completeness and credentials."""
import hashlib
import json
from pathlib import Path

import pytest

from tools.release_support import set_version, copy_runtime, collect_artifacts, validate_version


def test_version_is_consistent_across_desktop_and_android(tmp_path, monkeypatch):
    (tmp_path/'android/dosidicus_mobile').mkdir(parents=True)
    (tmp_path/'version').write_text('dosidicus: old\nbrain_tool: keep\n')
    (tmp_path/'android/buildozer.spec').write_text('version = old\nandroid.numeric_version = 1\n')
    (tmp_path/'android/dosidicus_mobile/__init__.py').write_text('__version__ = "old-mobile"\n')
    monkeypatch.setenv('GITHUB_SHA', 'abc123')
    set_version(tmp_path, '3.2.7-canary.1')
    assert (tmp_path/'version').read_text() == 'dosidicus: 3.2.7-canary.1\nbrain_tool: keep\n'
    assert 'version = 3.2.7-canary.1\n' in (tmp_path/'android/buildozer.spec').read_text()
    assert 'android.numeric_version = 30207\n' in (tmp_path/'android/buildozer.spec').read_text()
    assert '3.2.7-canary.1-mobile' in (tmp_path/'android/dosidicus_mobile/__init__.py').read_text()
    assert json.loads((tmp_path/'release-info.json').read_text())['commit'] == 'abc123'


@pytest.mark.parametrize('version', ['', '../v3', '3.1.2\nkey=value', '3.1.2; echo test',
                                     'v3.1.2', '3.1', '03.1.2', '3.100.0', '3.0.100', '0.0.0'])
def test_invalid_release_versions_are_rejected(version):
    with pytest.raises(ValueError):
        validate_version(version)


def test_runtime_assembly_omits_repository_credentials_and_unrelated_builds(tmp_path):
    for name in ('images', 'src', 'plugins', '.git', 'android/releases'):
        (tmp_path/name).mkdir(parents=True)
        (tmp_path/name/'data.txt').write_text(name)
    (tmp_path/'config.ini').write_text('[General]\n')
    (tmp_path/'version').write_text('dosidicus: 3.2.7\n')
    target = tmp_path/'output'
    copy_runtime(tmp_path, target)
    assert (target/'images/data.txt').read_text() == 'images'
    assert (target/'src/data.txt').is_file()
    assert not (target/'.git').exists()
    assert not (target/'android').exists()
    assert not (target/'output').exists()


ARTIFACTS = ('Dosidicus-windows.zip', 'Dosidicus-windows-arm64.zip',
             'Dosidicus-macos-arm64.zip', 'Dosidicus-macos-arm64-debug.zip',
             'Dosidicus-macos-arm64.dmg', 'Dosidicus-macos-x64.dmg',
             'Dosidicus-macos-x64.zip', 'Dosidicus-macos-x64-debug.zip',
             'Dosidicus-linux.tar.gz', 'dosidicus-3.2.7-arm64-release.apk')


def test_release_requires_all_architectures_and_checksums_every_asset(tmp_path):
    source, target = tmp_path/'builds', tmp_path/'release'
    source.mkdir()
    for name in ARTIFACTS:
        (source/name).write_bytes(name.encode())
    collect_artifacts(source, target, '3.2.7')
    manifest = json.loads((target/'release-info.json').read_text())
    assert len(manifest['artifacts']) == 10
    assert (target/'Dosidicus-3.2.7-macos-arm64.dmg').is_file()
    assert (target/'Dosidicus-3.2.7-macos-x64.dmg').is_file()
    hashes = (target/'SHA256SUMS').read_text().splitlines()
    assert len(hashes) == 11
    for row in hashes:
        digest, name = row.split('  ')
        assert hashlib.sha256((target/name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('missing', ['Dosidicus-macos-arm64.dmg', 'Dosidicus-macos-x64.dmg'])
def test_release_requires_both_macos_installers(tmp_path, missing):
    source = tmp_path/'builds'; source.mkdir()
    for name in ARTIFACTS:
        if name != missing:
            (source/name).write_bytes(b'artifact')
    with pytest.raises(ValueError, match=missing):
        collect_artifacts(source, tmp_path/'release', '3.2.7')


def test_unsigned_android_output_cannot_satisfy_a_release(tmp_path):
    source = tmp_path/'builds'; source.mkdir()
    for name in ARTIFACTS[:-1]:
        (source/name).write_bytes(b'artifact')
    (source/'dosidicus-3.2.7-arm64-release-unsigned.apk').write_bytes(b'unsigned')
    with pytest.raises(ValueError, match='release.apk'):
        collect_artifacts(source, tmp_path/'release', '3.2.7')

