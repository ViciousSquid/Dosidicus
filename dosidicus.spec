# -*- mode: python ; coding: utf-8 -*-
# dosidicus.spec — PyInstaller build spec for Dosidicus
# Place this file in the project root alongside main.py

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ---------------------------------------------------------------------------
# Data files — bundled into the executable / app bundle
# ---------------------------------------------------------------------------
datas = [
    # Source assets
    ('src/arcade.ttf',            'src'),
    ('src/decoration_stats.json', 'src'),

    # Runtime data
    ('custom_brains',             'custom_brains'),
    ('example_squids',            'example_squids'),
    ('images',                    'images'),

    # Plugins shipped with the app
    ('plugins',                   'plugins'),

    # Top-level files
    ('config.ini',                '.'),
    ('version',                   '.'),
    ('SaveViewer.html',           '.'),
]

# ---------------------------------------------------------------------------
# Hidden imports — modules that are loaded dynamically at runtime
# ---------------------------------------------------------------------------
hidden_imports = [
    # Plugin packages
    *collect_submodules('plugins.achievements'),
    *collect_submodules('plugins.multiplayer'),

    # Common PyQt5 bits that PyInstaller sometimes misses
    'PyQt5.sip',
    'PyQt5.QtPrintSupport',
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim unused heavy stdlib modules to keep size down
        'tkinter', 'unittest', 'email', 'html', 'http',
        'xmlrpc', 'pydoc', 'doctest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------------------
# Build — one-directory output (more reliable for PyQt5 + plugins)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir mode
    name='Dosidicus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX can break PyQt5 DLLs
    console=False,                  # no terminal window
    icon=None,                      # add an .ico / .icns path here if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Dosidicus',
)

# macOS — wrap the directory into a .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Dosidicus.app',
        icon=None,
        bundle_identifier='com.vicioussquid.dosidicus',
        info_plist={
            'CFBundleShortVersionString': '2.6.1',
            'NSHighResolutionCapable': True,
        },
    )
