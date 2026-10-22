"""macOS application bundle working-directory regression tests."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from src.macos_runtime import prepare_macos_runtime


class MacOSRuntimeTests(unittest.TestCase):
    def test_bundled_resources_and_user_data_are_separated(self):
        with tempfile.TemporaryDirectory() as temp:
            # macOS temp dirs live under /var, a symlink to /private/var, and
            # Path.cwd() reports the resolved path after chdir.
            root = Path(temp).resolve()
            resources = root / "Dosidicus.app" / "Contents" / "MacOS"
            resources.mkdir(parents=True)
            binary = resources / "Dosidicus"
            binary.touch()
            (resources / "images").mkdir()
            (resources / "images" / "icon.png").write_bytes(b"icon")
            (resources / "plugins").mkdir()
            (resources / "config.ini").write_text("[General]\nlanguage = en\n")
            (resources / "custom_brains").mkdir()
            (resources / "custom_brains" / "default.json").write_text("{}")
            data = root / "App Support" / "Dosidicus"
            old_cwd = Path.cwd()
            try:
                result = prepare_macos_runtime(executable=binary, data_dir=data)
                self.assertEqual(result, data)
                self.assertEqual(Path.cwd(), data)
                self.assertTrue((data / "images").is_symlink())
                self.assertTrue((data / "images" / "icon.png").exists())
                self.assertTrue((data / "plugins").is_symlink())
                self.assertEqual((data / "config.ini").read_text(),
                                 "[General]\nlanguage = en\n")
                self.assertFalse((data / "custom_brains").is_symlink())
                self.assertTrue((data / "custom_brains" / "default.json").exists())
                (data / "config.ini").write_text("user settings")
                (data / "custom_brains" / "default.json").write_text("user brain")
                prepare_macos_runtime(executable=binary, data_dir=data)
                self.assertEqual((data / "config.ini").read_text(), "user settings")
                self.assertEqual((data / "custom_brains" / "default.json").read_text(),
                                 "user brain")
            finally:
                os.chdir(old_cwd)

    def test_relink_after_app_relocation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "data"
            old_cwd = Path.cwd()
            try:
                for label in ("old", "new"):
                    resources = root / label / "Dosidicus.app" / "Contents" / "MacOS"
                    resources.mkdir(parents=True)
                    (resources / "Dosidicus").touch()
                    (resources / "images").mkdir()
                    (resources / "images" / "marker").write_text(label)
                    prepare_macos_runtime(executable=resources / "Dosidicus",
                                          data_dir=data)
                    self.assertEqual((data / "images" / "marker").read_text(), label)
            finally:
                os.chdir(old_cwd)

    def test_normal_python_launch_does_not_change_directory(self):
        with patch("src.macos_runtime.sys.platform", "linux"):
            self.assertIsNone(prepare_macos_runtime())


if __name__ == "__main__":
    unittest.main()
