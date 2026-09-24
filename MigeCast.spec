# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MigeCast IPTV (Windows x64, one-folder build).
#
# The one-folder output (dist/MigeCast) is packed by Inno Setup into a single
# MigeCast-Setup-<version>.exe. A one-file PyInstaller EXE is intentionally NOT
# used: it unpacks ~150 MB (Qt + libVLC) to %TEMP% on every start, which is
# slow and often flagged by antivirus software. See docs/DISTRIBUTION.md.
#
# Prerequisites (done by .github/workflows/windows-build.yml):
#   vendor/vlc/libvlc.dll, vendor/vlc/libvlccore.dll, vendor/vlc/plugins/...
#   build/version_info.txt   (tools/stamp_version.py)
import os
from pathlib import Path

ROOT = Path(SPECPATH)
VLC_DIR = ROOT / "vendor" / "vlc"
if not (VLC_DIR / "libvlc.dll").exists():
    raise SystemExit("vendor/vlc/libvlc.dll missing - run the VLC download step first")

version_file = ROOT / "build" / "version_info.txt"

datas = [
    (str(ROOT / "resources" / "migecast.ico"), "resources"),
    (str(ROOT / "resources" / "migecast.png"), "resources"),
    (str(VLC_DIR), "vlc"),  # libVLC + plugins, copied as-is into _internal/vlc
]

excludes = [
    "unittest", "pydoc_data", "test", "numpy", "pandas", "matplotlib", "IPython",
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineQuick", "PyQt6.QtQml",
    "PyQt6.QtQuick", "PyQt6.QtQuick3D", "PyQt6.QtQuickWidgets", "PyQt6.Qt3DCore", "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets", "PyQt6.QtPdf", "PyQt6.QtPdfWidgets", "PyQt6.QtBluetooth",
    "PyQt6.QtPositioning", "PyQt6.QtSensors", "PyQt6.QtSerialPort", "PyQt6.QtSql", "PyQt6.QtTest",
    "PyQt6.QtDesigner", "PyQt6.QtHelp", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets", "PyQt6.QtSvg",
    "PyQt6.QtCharts", "PyQt6.QtDataVisualization", "PyQt6.QtNfc", "PyQt6.QtRemoteObjects",
    "PyQt6.QtSpatialAudio", "PyQt6.QtTextToSpeech", "PyQt6.QtWebChannel", "PyQt6.QtWebSockets",
    "PyQt6.QtXml", "PyQt6.QtDBus", "PyQt6.QtNetwork",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["sqlalchemy.dialects.sqlite"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

# Splash screen drawn by the bootloader right after double-click, before the
# Python runtime and the Qt DLLs are loaded (a cold first start can take a few
# seconds while Windows reads and virus-scans them). main.py closes it as soon
# as the main window is visible.
splash = Splash(
    str(ROOT / "resources" / "splash.png"),
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    [],
    exclude_binaries=True,
    name="MigeCast",
    icon=str(ROOT / "resources" / "migecast.ico"),
    version=str(version_file) if version_file.exists() else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX-packed binaries trigger antivirus false positives
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    splash.binaries,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MigeCast",
)
