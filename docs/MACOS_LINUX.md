# ARGUS for macOS and Linux

ARGUS ships as one app per system. With no arguments it opens the CLI when
started from a terminal, and the desktop window when started from Finder, the
Dock or an app menu. `argus desktop` opens the window from a terminal.

| System | Download | Installs |
|---|---|---|
| macOS 13+ on Apple silicon (arm64) | [`ARGUS-macos-arm64.dmg`](https://github.com/reenji/jarvis/releases/latest/download/ARGUS-macos-arm64.dmg) | `ARGUS.app` |
| Ubuntu 22.04+ / Debian 12+ (x86_64) | [`ARGUS-linux-x86_64.deb`](https://github.com/reenji/jarvis/releases/latest/download/ARGUS-linux-x86_64.deb) | `/usr/lib/argus`, the `argus` command and an app-menu entry |
| Other Linux (x86_64, glibc 2.35+) | [`ARGUS-linux-x86_64.tar.gz`](https://github.com/reenji/jarvis/releases/latest/download/ARGUS-linux-x86_64.tar.gz) | Portable folder; run `./argus/ARGUS` |

Each release lists `SHA256SUMS.txt`; check a download with
`shasum -a 256 <file>` (macOS) or `sha256sum <file>` (Linux).

## macOS

1. Open the disk image and drag **ARGUS** to **Applications**.
2. The app is not signed or notarized yet, so the first open is blocked.
   Right-click **ARGUS** in Applications and choose **Open**, then **Open**
   again. On macOS 15, if there is no Open button, go to **System Settings →
   Privacy & Security** and choose **Open Anyway**.
3. Allow the microphone when asked (voice), and grant **Screen Recording** and
   **Accessibility** in Privacy & Security if you want screen and computer
   control.

To use `argus` in a terminal:

```bash
sudo ln -sf /Applications/ARGUS.app/Contents/MacOS/ARGUS /usr/local/bin/argus
argus setup
```

## Linux

```bash
sudo apt install ./ARGUS-linux-x86_64.deb
argus setup
```

`apt` installs the system libraries the app needs (Qt's X11/EGL libraries and
PortAudio). Open **Argus** from the app menu for the desktop window. With the
tarball, install those libraries yourself: `libegl1 libgl1 libxkbcommon-x11-0
libxcb-cursor0 libportaudio2` on Debian/Ubuntu.

## First run

`argus setup` stores the Gemini API key, or enter it when the desktop window
asks. The desktop app waits for two claps at startup; set
`ARGUS_SKIP_CLAP_GATE=1` to skip that. `argus doctor` checks the key, audio
devices and local storage.

## Where your data lives

The app itself is read-only, so keys, memory and outputs go to a per-user
folder:

- macOS: `~/Library/Application Support/Argus`
- Linux: `$XDG_DATA_HOME/argus` (default `~/.local/share/argus`)

Set `ARGUS_DATA_DIR` to use another folder. Uninstalling (drag the app to the
Trash, or `sudo apt remove argus`) leaves that folder in place.

## Build it yourself

`.github/workflows/release.yml` builds macOS on `macos-14` and Linux on
`ubuntu-22.04` next to Windows. Locally, with Python 3.12:

```bash
python -m pip install -r requirements.txt . pyinstaller==6.22.3
pyinstaller --noconfirm ARGUS.spec
scripts/smoke_unix_build.sh dist/ARGUS/ARGUS           # Linux
scripts/package_linux.sh 0.3.0                          # .deb + .tar.gz (needs dpkg-deb)
scripts/smoke_unix_build.sh dist/ARGUS.app/Contents/MacOS/ARGUS   # macOS
scripts/package_macos.sh                                # .dmg
```
