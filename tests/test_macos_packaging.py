"""Regression checks for running a signed macOS bundle from read-only media."""

import hashlib
from pathlib import Path
import sys

from src import runtime_paths


def fake_bundle(monkeypatch, tmp_path):
    bundle = tmp_path / "read-only-app"
    for name, content in {
        "config.ini": "[General]\nlanguage = en\n[Compute]\nbackend = numpy\n",
        "images/poop1.png": "image-v1",
        "plugins/multiplayer/main.py": "# bundled plugin v1",
        "plugins/whitelist.txt": "achievements",
        "custom_brains/default.json": "{}",
        "src/arcade.ttf": "font",
    }.items():
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "argv", ["Dosidicus"])
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")
    monkeypatch.chdir(tmp_path)
    return bundle


def fingerprint(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


def test_launch_seeds_writable_data_without_changing_bundle(monkeypatch, tmp_path):
    bundle = fake_bundle(monkeypatch, tmp_path)
    original = fingerprint(bundle)
    runtime_paths.prepare_macos_runtime()
    destination = runtime_paths.runtime_data_dir()
    assert destination == tmp_path / "user/Library/Application Support/Dosidicus"
    assert Path.cwd() == destination
    for name in ("config.ini", "images/poop1.png", "src/arcade.ttf", "saves", "_memory", "logs", "exports"):
        assert (destination / name).exists()
    assert fingerprint(bundle) == original


def test_relaunch_preserves_user_data_and_updates_builtin_code(monkeypatch, tmp_path):
    bundle = fake_bundle(monkeypatch, tmp_path)
    runtime_paths.prepare_macos_runtime()
    destination = runtime_paths.runtime_data_dir()
    user_data = {
        "config.ini": "custom settings",
        "saves/pet.json": "my squid",
        "_memory/LongTerm.json": "my memories",
        "custom_brains/default.json": "my edited brain",
        "plugins/whitelist.txt": "custom whitelist",
        "plugins/my_plugin/main.py": "# my custom plugin",
    }
    for name, content in user_data.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (bundle / "plugins/multiplayer/main.py").write_text("# bundled plugin v2")
    runtime_paths.prepare_macos_runtime()
    for name, content in user_data.items():
        assert (destination / name).read_text() == content
    assert (destination / "plugins/multiplayer/main.py").read_text() == "# bundled plugin v2"


def test_config_and_backend_use_writable_settings(monkeypatch, tmp_path):
    from src.config_manager import ConfigManager
    from src.compute_backend import _read_backend_from_config
    fake_bundle(monkeypatch, tmp_path)
    runtime_paths.prepare_macos_runtime()
    config = ConfigManager()
    assert Path(config.config_path) == runtime_paths.runtime_data_dir() / "config.ini"
    assert _read_backend_from_config() == "numpy"


def test_source_launch_does_not_change_directory_or_create_data(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    runtime_paths.prepare_macos_runtime()
    assert Path.cwd() == tmp_path
    assert list(tmp_path.iterdir()) == []


def test_smoke_data_override_only_applies_to_smoke_test(monkeypatch, tmp_path):
    fake_bundle(monkeypatch, tmp_path)
    monkeypatch.setenv("DOSIDICUS_SMOKE_DATA_DIR", str(tmp_path / "smoke"))
    assert runtime_paths.runtime_data_dir() != tmp_path / "smoke"
    monkeypatch.setattr(sys, "argv", ["Dosidicus", "--smoke-test"])
    assert runtime_paths.runtime_data_dir() == tmp_path / "smoke"


def test_brain_bridge_uses_the_same_writable_store(monkeypatch, tmp_path):
    from src.brain_state_bridge import get_bridge_directory
    fake_bundle(monkeypatch, tmp_path)
    assert get_bridge_directory() == runtime_paths.runtime_data_dir() / "bridge"


def test_startup_exception_without_qapplication_preserves_traceback(monkeypatch, capsys):
    import main
    monkeypatch.setattr(main.QtWidgets.QApplication, "instance", lambda: None)
    def unexpected_dialog(*args, **kwargs):
        raise AssertionError("A startup exception must not create a QWidget before QApplication")
    monkeypatch.setattr(main.QtWidgets.QMessageBox, "critical", unexpected_dialog)
    main.global_exception_handler(ValueError, ValueError("original startup failure"), None)
    assert "original startup failure" in capsys.readouterr().err
