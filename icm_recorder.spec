# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ICM2 BLE ECG Recorder.

Build with: pyinstaller --noconfirm icm_recorder.spec
Output: dist/icm_recorder.exe (single file)

Required collect_all packages:
  - bleak: BLE library with winrt backend
  - winrt: Windows Runtime bindings (bleak dependency on Windows)
  - PyQt5: GUI framework
  - pyqtgraph: real-time plotting
  - cryptography: AES encryption for handshake
"""

from PyInstaller.utils.hooks import collect_all

# Collect all submodules and data for these packages
collect_all_packages = ['bleak', 'winrt', 'PyQt5', 'pyqtgraph', 'cryptography']

all_datas = []
all_binaries = []
all_hiddenimports = []

for pkg in collect_all_packages:
    datas, binaries, hiddenimports = collect_all(pkg)
    all_datas.extend(datas)
    all_binaries.extend(binaries)
    all_hiddenimports.extend(hiddenimports)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
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
    name='icm_recorder',
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
    icon=None,
)
