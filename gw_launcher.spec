# gw_launcher.spec
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports  = collect_submodules("PySide6") + collect_submodules("minecraft_launcher_lib")
hiddenimports += ["requests","urllib3","idna","certifi","charset_normalizer"]

datas = [("assets", "assets"), ("logo.png", ".")]
try:
    datas += collect_data_files("PySide6")
except Exception:
    pass

a = Analysis(
    ["gw_launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={"qt_plugins_binaries": True},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GWLauncher",
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
    version="file_version_info.txt",
)
