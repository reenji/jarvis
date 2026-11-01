# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller --noconfirm ARGUS.spec
#
# Windows output (dist/ARGUS/):
#   ARGUS.exe  windowed; a double click opens the desktop assistant
#   argus.com  console; `argus chat`, `argus setup`, `argus doctor` in a terminal
# Both run argus_launcher.py. contents_directory='.' keeps config/, core/ and
# memory/ beside the executables, where the app reads and writes them.

import os
import sys
from pathlib import Path

APP_PACKAGES = [
    'actions', 'agent', 'audio', 'awareness', 'cli', 'config', 'core',
    'llm_providers', 'memory', 'observability', 'plugins', 'tools', 'ui',
]


def package_modules(package):
    # Walk the source tree instead of importing it: importing ui/ needs Qt and
    # a working display, and a failed import silently drops its submodules.
    root = Path(SPECPATH)
    for path in sorted((root / package).rglob('*.py')):
        parts = path.relative_to(root).with_suffix('').parts
        if 'tests' in parts:
            continue
        if parts[-1] == '__init__':
            parts = parts[:-1]
        yield '.'.join(parts)


hiddenimports = ['main']
for package in APP_PACKAGES:
    # main.py and ui/ load modules by name at runtime, so static analysis misses them.
    hiddenimports += package_modules(package)

a = Analysis(
    ['argus_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/fonts', 'assets/fonts'),
        ('assets/argus.ico', 'assets'),
        ('core/prompt.txt', 'core'),
        ('config/*.example.json', 'config'),
        ('memory/*.example.json', 'memory'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

common = dict(
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/argus.ico',
    contents_directory='.',
)

desktop_exe = EXE(pyz, a.scripts, [], name='ARGUS', console=False, **common)
executables = [desktop_exe]
if sys.platform == 'win32':
    # PyInstaller always appends .exe on Windows; renamed to argus.com below.
    executables.append(EXE(pyz, a.scripts, [], name='argus-console', console=True, **common))

coll = COLLECT(
    *executables,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ARGUS',
)

if sys.platform == 'win32':
    bundle = os.path.join(DISTPATH, 'ARGUS')
    os.replace(os.path.join(bundle, 'argus-console.exe'), os.path.join(bundle, 'argus.com'))

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='ARGUS.app',
        icon=None,
        bundle_identifier=None,
    )
