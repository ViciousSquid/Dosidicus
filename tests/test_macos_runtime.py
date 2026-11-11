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
            root = Path(temp)
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
                # Resolved: on a Mac the temporary folder is /var/..., a link
                # to /private/var/..., and the working directory is reported
                # by where it really is.
                self.assertEqual(Path.cwd().resolve(), data.resolve())
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

    def test_a_link_left_by_an_older_app_that_has_gone_does_not_stop_the_game(self):
        """A player's settings folder from an earlier build held links into
        that app. With the app gone the links point nowhere, and the copy
        that replaces them used to fail on the link itself: the game never
        opened (FileExistsError ... Dosidicus/custom_brains)."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            resources = root / "Dosidicus.app" / "Contents" / "MacOS"
            resources.mkdir(parents=True)
            binary = resources / "Dosidicus"
            binary.touch()
            (resources / "config.ini").write_text("[General]\nlanguage = en\n")
            (resources / "custom_brains").mkdir()
            (resources / "custom_brains" / "default.json").write_text("{}")
            data = root / "App Support" / "Dosidicus"
            data.mkdir(parents=True)
            gone = root / "Old.app" / "Contents" / "MacOS"
            (data / "custom_brains").symlink_to(gone / "custom_brains", target_is_directory=True)
            (data / "config.ini").symlink_to(gone / "config.ini")
            old_cwd = Path.cwd()
            try:
                self.assertEqual(prepare_macos_runtime(executable=binary, data_dir=data), data)
                self.assertFalse((data / "custom_brains").is_symlink())
                self.assertTrue((data / "custom_brains" / "default.json").exists())
                self.assertFalse((data / "config.ini").is_symlink())
                self.assertIn("language = en", (data / "config.ini").read_text())
            finally:
                os.chdir(old_cwd)

    def test_a_link_the_player_made_that_still_leads_somewhere_is_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            resources = root / "Dosidicus.app" / "Contents" / "MacOS"
            resources.mkdir(parents=True)
            binary = resources / "Dosidicus"
            binary.touch()
            (resources / "custom_brains").mkdir()
            mine = root / "My Brains"
            mine.mkdir()
            (mine / "clever.json").write_text("{}")
            data = root / "App Support" / "Dosidicus"
            data.mkdir(parents=True)
            (data / "custom_brains").symlink_to(mine, target_is_directory=True)
            old_cwd = Path.cwd()
            try:
                prepare_macos_runtime(executable=binary, data_dir=data)
                self.assertTrue((data / "custom_brains").is_symlink())
                self.assertTrue((data / "custom_brains" / "clever.json").exists())
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
