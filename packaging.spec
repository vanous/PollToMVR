# -*- mode: python ; coding: utf-8 -*-
# to convert the png to ico, use:
# magick convert MVRtoKuma_icon.png -define icon:auto-resize=512,256,128,64,48,32,16 MVRtoKuma.ico

import sys
from PyInstaller.building.build_main import EXE
# (other imports like Analysis, PYZ, etc.)

icon_file = "images/PollToMVR_icon.ico"

if sys.platform.startswith('win'):
    exe_name = 'PollToMVR_windows'
elif sys.platform.startswith('linux'):
    exe_name = 'PollToMVR_linux'
    icon_file = "images/MVRtoKuma_icon.png"
else:
    exe_name = 'PollToMVR_macos'

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('tui/*.css', 'tui')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name=f'{exe_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    icon=icon_file,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
