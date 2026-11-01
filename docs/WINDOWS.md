# ARGUS for Windows

ARGUS ships for Windows 10 and 11 (x64) as one app with two ways in:

| Executable | Opens | How to start it |
|---|---|---|
| `ARGUS.exe` | The desktop assistant (window, voice, panels) | Start menu **Argus**, desktop shortcut, or a double click |
| `argus.com` | The terminal CLI | Start menu **Argus Terminal**, or type `argus` in any terminal |

Both live in the same folder. In `cmd` and PowerShell, `argus` resolves to
`argus.com` before `ARGUS.exe` (PATHEXT order), so terminal commands such as
`argus chat`, `argus setup`, `argus doctor` and `argus -q "..."` run in the
console. `argus desktop` opens the desktop window from a terminal.

## Install

Download from the [latest release](https://github.com/reenji/jarvis/releases/latest)
on GitHub:

- [`ARGUS-windows-x64-setup.exe`](https://github.com/reenji/jarvis/releases/latest/download/ARGUS-windows-x64-setup.exe): installer. It installs for the current user
  only (no administrator prompt) in `%LOCALAPPDATA%\Programs\Argus`, adds
  Start menu shortcuts, and adds the folder to your user `PATH` so `argus`
  works in new terminals. Uncheck that task to skip the `PATH` change.
- [`ARGUS-windows-x64-portable.zip`](https://github.com/reenji/jarvis/releases/latest/download/ARGUS-windows-x64-portable.zip): portable copy. Extract it anywhere you
  can write to and run `ARGUS.exe` or `argus.com` from that folder.

Each release also lists `SHA256SUMS.txt` to check the downloads against
(`Get-FileHash <file>` in PowerShell).

The build is not code-signed yet, so SmartScreen may warn on first run. Choose
**More info → Run anyway**.

## First run

1. Run `argus setup` in a terminal, or open **Argus** and enter your Gemini
   API key when the window asks for it.
2. The desktop app waits for **two claps** at startup before it opens. Set
   the user environment variable `ARGUS_SKIP_CLAP_GATE=1` to skip that gate.
3. `argus doctor` checks the key, voice devices and local storage.

## Where your data lives

The app keeps `config\`, `memory\`, `outputs\` and an optional `.env` in its
install folder, next to the executables. Upgrading with a newer installer
replaces only the shipped files, so keys and memory stay. Uninstalling removes
the program and its `PATH` entry but leaves those folders; delete the install
folder by hand to remove them. The terminal CLI also stores settings and
sessions in its per-user ARGUS home.

## Build it yourself

The `Windows build` workflow (`.github/workflows/windows.yml`) builds on
`windows-latest` for pull requests that touch packaging, on manual dispatch,
and on `v*` tags. A tag also publishes the installer and zip as a GitHub
release:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

To build locally on Windows with Python 3.12 and Inno Setup 6:

```powershell
python -m pip install -r requirements.txt . pyinstaller==6.22.3
pyinstaller --noconfirm ARGUS.spec
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=0.2.0 installer\argus.iss
```

`dist\ARGUS\` holds the portable app and `dist\ARGUS-windows-x64-setup.exe`
the installer. File names carry no version, so `releases/latest/download/`
links keep working; the version shows in the release title and the installer.
The app icon is the pixel art in `assets/argus-icon.png` (one image pixel per
art pixel, square). After changing it, run `python scripts/make_windows_icon.py`
to rebuild `assets/argus.ico`, which the executables, the installer and the
desktop window and tray use.
