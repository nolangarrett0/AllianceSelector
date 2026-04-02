# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['sklearn.ensemble._forest', 'sklearn.tree._tree', 'sklearn.neighbors._typedefs', 'sklearn.neighbors._quad_tree', 'sklearn.utils._typedefs', 'sklearn.utils._cython_blas', 'numpy', 'pandas', 'flask', 'flask_cors']
hiddenimports += collect_submodules('sklearn')


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('index.html', '.'), ('vex_scout_v11.py', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VEX Scout',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VEX Scout',
)
