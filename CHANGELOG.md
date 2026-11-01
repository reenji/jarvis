# Changelog

Notable changes to ARGUS are recorded here. This file tracks the current
unreleased repository work; it does not imply a published release.

## Unreleased — 2026-10-02

### Added

- Added the Windows app: one PyInstaller bundle with `ARGUS.exe` (desktop)
  and `argus.com` (terminal CLI), a per-user Inno Setup installer, a portable
  zip, and a `Windows build` workflow that publishes both on `v*` tags. See
  [`docs/WINDOWS.md`](docs/WINDOWS.md).
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
