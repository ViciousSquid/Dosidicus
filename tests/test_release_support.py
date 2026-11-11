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
             'Dosidicus-macos-universal.dmg',
             'Dosidicus-linux.tar.gz', 'dosidicus-3.2.7-arm64-release.apk')


def test_release_requires_all_architectures_and_checksums_every_asset(tmp_path):
    source, target = tmp_path/'builds', tmp_path/'release'
    source.mkdir()
    for name in ARTIFACTS:
        (source/name).write_bytes(name.encode())
    collect_artifacts(source, target, '3.2.7')
    manifest = json.loads((target/'release-info.json').read_text())
    assert len(manifest['artifacts']) == 11
    assert (target/'Dosidicus-3.2.7-macos-arm64.dmg').is_file()
    assert (target/'Dosidicus-3.2.7-macos-x64.dmg').is_file()
    assert (target/'Dosidicus-3.2.7-macos-universal.dmg').is_file()
    hashes = (target/'SHA256SUMS').read_text().splitlines()
    assert len(hashes) == 12
    for row in hashes:
        digest, name = row.split('  ')
        assert hashlib.sha256((target/name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('missing', ['Dosidicus-macos-arm64.dmg', 'Dosidicus-macos-x64.dmg',
                                     'Dosidicus-macos-universal.dmg'])
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



# ---- a build run by hand is a release ---------------------------------------
from tools.release_support import plan_build      # noqa: E402

BY_HAND = {'BY_HAND': 'true', 'HAS_KEYSTORE': 'true', 'GITHUB_RUN_NUMBER': '74'}


def _root(tmp_path, version='3.2.0'):
    (tmp_path / 'version').write_text(f'dosidicus: {version}\nbrain_tool: 20.10.26\n')
    return tmp_path


def test_a_build_run_by_hand_is_a_prerelease_named_after_the_version_and_the_run(tmp_path):
    assert plan_build(BY_HAND, _root(tmp_path)) == {
        'version': '3.2.0-build.74', 'tag': 'v3.2.0-build.74',
        'prerelease': 'true', 'release': 'true'}
    # A four-part version file still gives a version Android can take.
    assert plan_build(BY_HAND, _root(tmp_path, '3.2.0.0'))['tag'] == 'v3.2.0-build.74'


def test_a_tag_typed_in_is_used_and_is_stable_unless_asked_otherwise(tmp_path):
    root = _root(tmp_path)
    assert plan_build(dict(BY_HAND, REQUESTED_TAG='v3.2.1'), root) == {
        'version': '3.2.1', 'tag': 'v3.2.1', 'prerelease': 'false', 'release': 'true'}
    assert plan_build(dict(BY_HAND, REQUESTED_TAG='v3.2.1', REQUESTED_PRERELEASE='true'),
                      root)['prerelease'] == 'true'
    for bad in ('3.2.1', 'vlatest', 'v3.2'):
        with pytest.raises(ValueError):
            plan_build(dict(BY_HAND, REQUESTED_TAG=bad), root)
    with pytest.raises(ValueError, match='already exists'):
        plan_build(dict(BY_HAND, REQUESTED_TAG='v3.2.1'), root, lambda tag: tag == 'v3.2.1')


def test_without_the_signing_key_nothing_is_built_and_the_reason_is_given(tmp_path):
    with pytest.raises(ValueError, match='ANDROID_KEYSTORE_BASE64'):
        plan_build(dict(BY_HAND, HAS_KEYSTORE='false'), _root(tmp_path))


def test_a_push_only_builds_and_a_called_build_leaves_publishing_to_its_caller(tmp_path):
    root = _root(tmp_path)
    assert plan_build({'BY_HAND': 'false'}, root) == {
        'version': '', 'tag': '', 'prerelease': 'false', 'release': 'false'}
    assert plan_build({'CALLED_WITH_VERSION': '3.1.3-canary.1', 'BY_HAND': 'false'}, root) == {
        'version': '3.1.3-canary.1', 'tag': '', 'prerelease': 'false', 'release': 'false'}


def test_the_build_workflow_publishes_only_after_every_build_and_shares_the_publish_step():
    import yaml
    root = Path(__file__).resolve().parents[1] / '.github' / 'workflows'
    build = yaml.safe_load((root / 'build-nuitka.yml').read_text())
    jobs = build['jobs']
    assert set(jobs['release']['needs']) == {'plan', 'build', 'macos-universal-intel',
                                             'windows-arm64', 'android'}
    for name in ('windows-arm64', 'android', 'release'):
        assert jobs[name]['if'] == "needs.plan.outputs.release == 'true'"
    assert jobs['release']['uses'] == './.github/workflows/publish-release.yml'
    assert jobs['android']['uses'] == './.github/workflows/android-release.yml'
    assert jobs['release']['permissions'] == {'contents': 'write'}
    release = yaml.safe_load((root / 'release.yml').read_text())
    assert release['jobs']['publish']['uses'] == jobs['release']['uses']
