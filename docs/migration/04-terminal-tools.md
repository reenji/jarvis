# Phase 4: terminal and desktop tools

## Screen interaction

`screen_control` can inspect the active app or carry out a clear, multi-step
request with one visual observation and one action at a time. It prefers named
accessibility controls, falls back to coordinates scoped to the captured
window, and checks the result before reporting success. If the requested app is
closed, ARGUS can launch it, bring its window forward, and wait before acting.

The ARGUS terminal and shell windows are protected as screen targets. Screen
runs stop after at most 12 actions or 60 seconds by default. The bounds can be
configured with `ARGUS_SCREEN_MAX_STEPS` (1–30) and
`ARGUS_SCREEN_MAX_SECONDS` (5–180). After focusing an app, ARGUS waits 0.75
seconds by default; `ARGUS_SCREEN_FOCUS_DELAY` accepts 0–10 seconds. The
emergency stop hotkey defaults to `ctrl+alt+shift+esc` and can be changed with
`ARGUS_SCREEN_KILL_SWITCH`.

Direct user requests authorize ordinary mouse and keyboard actions, so the
agent does not ask for per-click approval. Before sharing a file that appears
to contain credentials, environment settings, Docker configuration, or other
sensitive material, ARGUS asks about that specific file without displaying
secret values. Merely opening or editing the file does not trigger this guard.

When a browser displays a CAPTCHA or other anti-bot check, ARGUS stops without
clicking the challenge, retrying the search, or attempting to bypass it. The
CLI can wait while the user resolves the challenge manually; it resumes the
original request once and stops if the challenge is still present.

Screen focus, window metadata, and interaction currently use the Windows
desktop backend. `argus doctor` reports full screen input as unavailable on
other platforms. App launching and text-only use remain available there.

## Diagnostics

Screen images are never persisted by default. To save diagnostic captures for
a run, pass `--debug-screens` to the CLI or set `ARGUS_DEBUG_SCREENSHOTS=true`.
The files are stored locally under the per-user ARGUS data directory at
`debug/screens/<run-id>/`.

Focused automated checks use mocked windows, input devices, vision responses,
and clients. They cover terminal protection, bounded steps and time, app focus
delay, anti-bot stopping and manual resumption, sensitive file sharing, and
opt-in screenshot storage. They do not use a real desktop, send real input, or
make live model requests. A manual Windows desktop validation is still needed
before the desktop app can be retired.
