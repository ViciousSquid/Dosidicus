"""The phone app draws with the desktop game's pictures - one copy of each."""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / 'android'


def _prepare_apk():
    spec = importlib.util.spec_from_file_location('prepare_apk', ANDROID / 'prepare_apk.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_listed_image_exists_in_the_desktop_images_folder():
    listed = _prepare_apk().mobile_assets()
    assert len(listed) == len(set(listed)) and len(listed) > 50
    missing = [name for name in listed if not (ROOT / 'images' / name).is_file()]
    assert not missing


def test_no_image_is_kept_twice():
    """android/assets holds only what the desktop game has no use for."""
    duplicated = [path.relative_to(ANDROID / 'assets').as_posix()
                  for path in (ANDROID / 'assets').rglob('*')
                  if path.is_file() and (ROOT / 'images' / path.relative_to(ANDROID / 'assets')).is_file()]
    assert not duplicated


def test_staging_puts_every_image_in_the_apk(tmp_path):
    module = _prepare_apk()
    staged = module.prepare(tmp_path)
    for name in module.mobile_assets():
        assert (staged / 'assets' / name).read_bytes() == (ROOT / 'images' / name).read_bytes()
    # buildozer.spec names these two by path.
    assert (staged / 'assets' / 'icon.png').is_file()
    assert (staged / 'assets' / 'presplash.png').is_file()
    # Every decoration in the palette is one the desktop game has.
    decorations = sorted(p.name for p in (staged / 'assets' / 'decoration').glob('*.png'))
    assert decorations == sorted(p.name for p in (ROOT / 'images' / 'decoration').glob('*.png'))


def test_the_app_finds_its_images_in_a_checkout_and_in_an_apk(tmp_path):
    in_checkout = _load(ANDROID / 'dosidicus_mobile' / 'ui' / 'assets.py', 'assets_in_checkout')
    assert os.path.samefile(in_checkout.ASSET_DIR, ROOT / 'images')
    assert os.path.isfile(in_checkout.asset('left1.png'))
    assert os.path.isfile(in_checkout.asset(os.path.join('decoration', 'castle.png')))

    staged = _prepare_apk().prepare(tmp_path)
    in_apk = _load(staged / 'dosidicus_mobile' / 'ui' / 'assets.py', 'assets_in_apk')
    assert os.path.samefile(in_apk.ASSET_DIR, staged / 'assets')
    assert os.path.isfile(in_apk.asset('left1.png'))
