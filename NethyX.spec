# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['proxy_scraper.py'],
    pathex=[],
    binaries=[],
    datas=[('prxy.ico', '.')], 
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
plist = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    plist,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='proxy_scraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='prxy.ico', 
)