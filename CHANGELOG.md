# Changelog

Notable changes to ARGUS are recorded here. This file tracks the current
unreleased repository work; it does not imply a published release.

## 0.3.2 — 2026-11-20

### Changed

- The free plan, which has no license key, now has daily limits: 25 text
  messages and 5 web searches per UTC day, the same as the free row of the
  site's plan table. Paid plans get their limits in the signed token. See
  [`docs/LICENSING.md`](docs/LICENSING.md#daily-limits) (#64).

## 0.3.1 — 2026-11-20

### Fixed

- Reminder notifications, the YouTube URL dialog, the onboarding log and the
  automation research prompt show ARGUS instead of the old J.A.R.V.I.S and
  MARK XXXIX names (#59).
- `main`, the TTS engine, screen processing and the audio backend import
  `sounddevice` only when audio is used, so the app and the test suite start
  on machines without a working audio server (#60).

### Changed

- The migration status and decisions record that the desktop app stays next
  to the CLI (#61).

## 0.3.0 and earlier — 2026-11-01

### Added

- Added macOS (arm64 `.dmg`) and Linux (x86_64 `.deb` and `.tar.gz`) builds
  to the `Build and release` workflow (formerly `Windows build`), with smoke
  tests of the installed, read-only app. On macOS and Linux one executable
  opens the CLI in a terminal and the desktop window otherwise. Version 0.3.0.
  See [`docs/MACOS_LINUX.md`](docs/MACOS_LINUX.md).
- Added the Windows app: one PyInstaller bundle with `ARGUS.exe` (desktop)
  and `argus.com` (terminal CLI), a per-user Inno Setup installer, a portable
  zip, and a `Windows build` workflow that publishes both on `v*` tags. See
  [`docs/WINDOWS.md`](docs/WINDOWS.md). Version 0.2.0; the CLI reads its version
  from `cli.__version__` when package metadata is absent.
- Reorganized the PyQt desktop interface into the `ui/` package while retaining
  its public import surface.
- Added a shared token source for desktop and web, with event adapters and
  WCAG contrast checks.
- Added desktop and responsive web console interfaces, plus screenshot
  evidence for their states, settings, authentication, onboarding, and reduced
  motion.
- Expanded CI to run the complete Python test suite in headless Qt mode.
- Added desktop, hosted API, and development dependency profiles.

### Changed

- The Windows desktop app no longer flashes PowerShell or console windows:
  background subprocesses run hidden, and the HUD stops its PowerShell
  temperature probe when it fails and otherwise reads it every 15 s.
- Packaged builds read bundled files (prompt, fonts, icon) from the bundle and
  keep `config/`, `memory/`, `outputs/` and `.env` in a per-user data folder:
  beside `ARGUS.exe` on Windows (unchanged), `~/Library/Application Support/Argus`
  on macOS, `$XDG_DATA_HOME/argus` (default `~/.local/share/argus`) on Linux.
  `ARGUS_DATA_DIR` overrides it. Source checkouts still use the repository.
- New app icon from the pixel-art portrait in `assets/argus-icon.png`, used by
  `ARGUS.exe`, the installer, the desktop window and the tray. The window title,
  tray tooltip and setup screen now say ARGUS instead of J.A.R.V.I.S.
- The Windows build skips importing pywinauto while PyInstaller probes for DLL
  search paths, which crashed on CI; pywinauto is still bundled.
- The live session config defaults to voice until license entitlements
  load, instead of failing when `voice_enabled` is not set yet.
- The license client calls the Argus site gateway (`https://argusdev.pages.dev/api/license`)
  instead of the backend host, and renewal links point to `https://argusdev.pages.dev/planos/`.
  `ARGUS_LICENSE_API_URL` and `ARGUS_LICENSE_RENEW_URL` still override both.
- Updated the README clone command to use `anonymandk/argus` and added desktop
  and web previews.
- Rewrote `DESIGN.md` to describe the implemented shared tokens, layouts,
  accessibility, motion, and runtime-signal limits.
- Expanded contributor instructions with Python QA, web build, and screenshot
  commands.
- Moved the awareness-engine note into `docs/` and linked it from the one-line
  memory index.

### Audited

- Recorded the F6 shell and side-effect review in
  [`docs/ui/REALITY_CHECK_F6.md`](docs/ui/REALITY_CHECK_F6.md). Tool execution
  behavior was not changed by the audit.
