# packaging/pyinstaller.spec
# PyInstaller build specification for Dosidicus

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('src')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas + [
        ('images', 'images'),
        ('translations', 'translations'),
        ('custom_brains', 'custom_brains'),
        ('example_squids', 'example_squids'),
        ('config.ini', '.'),
        ('version', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    name='dosidicus',
    console=True
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='dosidicus'
)
