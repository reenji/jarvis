# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller --noconfirm ARGUS.spec
#
# Windows output (dist/ARGUS/):
#   ARGUS.exe  windowed; a double click opens the desktop assistant
#   argus.com  console; `argus chat`, `argus setup`, `argus doctor` in a terminal
# Both run argus_launcher.py. contents_directory='.' keeps config/, core/ and
# memory/ beside the executables, where the Windows app reads and writes them.
#
# Linux output (dist/ARGUS/ARGUS) and macOS output (dist/ARGUS.app): one
# executable; with no arguments it opens the CLI in a terminal and the desktop
# window otherwise. Their data lives in the user's folder (core/app_paths.py).

import os
import sys
import tomllib
from pathlib import Path

VERSION = tomllib.loads(Path(SPECPATH, 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']

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

# On Windows, PyInstaller imports every collected package in one child process to
# find DLL search paths. Importing pywinauto starts UI Automation over COM, which
# can crash that child on a headless runner (exit 0xC0000005). pywinauto is pure
# Python and adds no DLL paths, so it is left out of that probe only; it is still
# bundled.
PROBE_SKIP = ('pywinauto',)

if sys.platform == 'win32':
    import PyInstaller.building.build_main as build_main

    _find_binary_dependencies = build_main.find_binary_dependencies

    def find_binary_dependencies(binaries, import_packages, *args, **kwargs):
        probed = [
            name for name in import_packages
            if not any(name == skip or name.startswith(skip + '.') for skip in PROBE_SKIP)
        ]
        return _find_binary_dependencies(binaries, probed, *args, **kwargs)

    build_main.find_binary_dependencies = find_binary_dependencies

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
        icon='assets/argus.ico',  # converted to .icns by PyInstaller (needs Pillow)
        bundle_identifier='io.github.reenji.argus',
        info_plist={
            'CFBundleName': 'Argus',
            'CFBundleDisplayName': 'Argus',
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': VERSION,
            'NSHighResolutionCapable': True,
            # Without these, macOS stops the app when voice or screen tools start.
            'NSMicrophoneUsageDescription': 'Argus listens to your voice commands.',
            'NSAppleEventsUsageDescription': 'Argus controls apps you ask it to use.',
        },
    )
