"""The check a built game runs on itself: does multiplayer work in this copy?

`Dosidicus --network-self-test` (plugins/multiplayer/selftest.py) is what the
release build runs on Windows, macOS and Linux, inside the compiled game. Here
it is run from source, so the check itself is known to be sound.
"""
import io
import subprocess
import sys
from pathlib import Path

from plugins.multiplayer import selftest

ROOT = Path(__file__).resolve().parents[1]


def test_it_passes_from_source_and_says_what_it_checked():
    said = io.StringIO()
    assert selftest.run(said) == 0
    lines = said.getvalue().splitlines()
    assert lines[-1].startswith('Network self-test passed')
    assert all(line.startswith('ok') for line in lines[:-1])
    for what in ('mp_network_node is in this build', 'friend code is 15 characters',
                 'linked by friend code is heard by the other', 'hears it back'):
        assert any(what in line for line in lines), what


def test_a_check_that_fails_fails_the_run(monkeypatch):
    monkeypatch.setattr(selftest, 'checks', lambda: iter([('sockets open', False, 'no')]))
    said = io.StringIO()
    assert selftest.run(said) == 1
    assert 'FAIL  sockets open' in said.getvalue() and 'FAILED: 1 of 1' in said.getvalue()


def test_a_module_missing_from_the_build_is_named(monkeypatch):
    import importlib
    real = importlib.import_module

    def without_host_body(name, *a, **k):
        if name.endswith('.host_body'):
            raise ModuleNotFoundError("No module named 'plugins.multiplayer.host_body'")
        return real(name, *a, **k)
    monkeypatch.setattr(importlib, 'import_module', without_host_body)
    said = io.StringIO()
    assert selftest.run(said) == 1
    assert 'FAIL  host_body is in this build' in said.getvalue()


def test_the_game_runs_it_and_exits_without_opening_a_window(tmp_path):
    log = tmp_path / 'self-test.log'
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--network-self-test'],
                            capture_output=True, text=True, timeout=120, cwd=tmp_path,
                            env={**__import__('os').environ, 'DOSIDICUS_SELF_TEST_LOG': str(log),
                                 'QT_QPA_PLATFORM': 'offscreen'})
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Network self-test passed' in result.stdout
    assert 'Network self-test passed' in log.read_text()
