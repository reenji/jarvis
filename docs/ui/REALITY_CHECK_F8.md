# F8 Security Follow-up

Status: **PASS on the available Linux host.** The F6 shell-launch and dispatcher-approval findings have code fixes and regression coverage on this branch. No live message was sent, no power action ran, and no desktop application was opened during verification.

## Changes

- `actions/open_app.py` no longer passes Windows input to a shell. HTTP, HTTPS, mail, and Windows settings URIs use the Windows URI handler; unsupported schemes are rejected. Executables use an argument list with `shell=False`, and Start-menu fallback accepts only a bounded application name without shell/control characters.
- `actions/dev_agent.py` opens VS Code with `shell=False`. On Windows it resolves a real `Code.exe` instead of passing a `.cmd` or `.bat` launcher together with a project path.
- `actions/computer_settings.py` replaces both xrandr pipelines with argument-list calls and parses display/brightness values in Python.
- `core/tool_approval.py` adds volatile, one-use approvals bound to a completed later user turn, the exact tool arguments or pending-draft fingerprint, and a five-minute expiry. A same-turn model tool call or changed operation/draft cannot consume the approval.
- `main.py` applies the user's direct-control preference to mutating `computer_control` calls (enabled by default), while keeping later-turn approval for `dev_agent`, computer restart/shutdown, email send approval, and message approval. A direct message bypasses the extra confirmation only if the current transcript contains the platform, recipient, send intent, and verbatim message body.
- `agent/executor.py` blocks delegated plans from bypassing the live dispatcher for those sensitive actions. The planner prompt documents the same restriction.
- Tool declarations and `core/prompt.txt` explain the later-turn approval behavior and the explicit computer target required for power actions.

## Verification

- `tests/test_security_approvals.py`: **18 passed**. Covers turn-bound and exact-argument approval, message verification, main-dispatch gates, delegated-dispatch blocks, URI/metacharacter handling, VS Code launch arguments, and xrandr parsing.
- `ARGUS_QA_MODE=1 ARGUS_QA_WORKSPACE=.qa-artifacts/f8-qa-workspace QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/qa.py automated`: **6 checks passed, 0 failed; 318 tests passed**. QA report: `.qa-artifacts/20261002-061049/qa-report.md` (ignored, local only).
- `QT_QPA_PLATFORM=offscreen ARGUS_QA_MODE=1 .venv/bin/python -m pytest -q tests`: **318 passed** locally on the available display.
- Python compilation, `git diff --check`, and a source scan for `shell=True` in the three audited action modules passed.
- The repository audit still reports two inherited P2 items: broad exception handling and legacy Gemini SDK imports.

## Backend CI collection failure follow-up

After F0–F7 merged, GitHub Actions run [36995251714](https://github.com/anonymandk/argus/actions/runs/36995251714) passed the frontend job but failed backend test collection with exit code 2. The collection errors were environmental: `sounddevice` could not load PortAudio, PyAutoGUI had no `DISPLAY`, and PyQt6 could not load `libEGL.so.1`.

The workflow now installs `libportaudio2`, `libegl1`, and `xvfb`, and runs the Python suite under `xvfb-run`. The local host does not have `xvfb-run`; the full pytest suite passed against its existing display. The F8 GitHub Actions run passed both jobs: frontend and backend; backend reported **318 passed, 2 warnings**. [Run 36995955613](https://github.com/anonymandk/argus/actions/runs/36995955613).

## Limits

- Direct mouse and keyboard actions no longer require a separate confirmation for each input when the default-enabled preference is on. Users can turn it off in **Settings → Actions**; live input was not exercised by the checks above.

- Native Windows/macOS execution was unavailable. Windows URI and process behavior was covered with mocks on Linux; physical Windows and macOS validation remains outstanding.
- Approval uses recognized user-turn text and does not authenticate the speaker. A source that can inject recognized audio is indistinguishable from a person speaking to ARGUS; deployments needing stronger assurance should bind confirmation to a trusted UI or physical-presence signal.
- `open_app` now rejects non-allowlisted URI schemes. Windows applications that exist only as batch launchers will not be started unless their corresponding `Code.exe`/application executable is found.
- No live email, message, desktop, shutdown, or restart action was performed.
