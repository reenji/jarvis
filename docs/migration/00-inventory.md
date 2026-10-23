# Repository inventory for desktop-to-CLI migration

Snapshot: branch feat/app-automation-reliability at commit 146677e, stacked PR #23.
Repository: https://github.com/reenji/jarvis
This phase is read-only with respect to runtime code. The hosted API and web product are treated as preserved scope.

## Entry points and runtime boundaries

| Entry point | Current behavior | Migration note |
|---|---|---|
| pyproject.toml | Setuptools package; requires Python 3.11+; installs command argus via main:cli_main. | Keep the established command name, but replace its current desktop-launch behavior with a real CLI. Check package metadata and package discovery during packaging phase. |
| scripts/argus | Shell launcher that sets ARGUS_CLI=1 and invokes main.py from the repository or its local .venv. | Reuse or replace after the new CLI entry point is packaged; do not create a second unrelated launcher. |
| main.py:cli_main | Sets ARGUS_CLI=1 and calls main(). main() imports ui.ArgusUI, creates ArgusLive, starts its async voice/Gemini runner in a thread, then enters the Qt event loop. | The current command named CLI is a desktop bootstrap, not an interactive terminal client. This is the primary mixed boundary to extract. |
| scripts/setup_argus.py and scripts/setup_argus.* | Create a repository-local .venv, install requirements.txt, copy .env.example to .env, then instruct the user to launch. | These scripts are desktop/repository-oriented setup. Replace installation flow after the standalone package and argus setup are ready. |
| api.server:app | FastAPI service; creates ArgusLive with a WebSocketClient for hosted sessions. | Preserve as an independent hosted adapter; verify it remains importable after desktop extraction. |
| web/package.json | Next.js frontend, with dev/build/lint/typecheck scripts. | Preserve as the hosted browser client. |
| docker-compose.yml / deployment manifests | Local API+web stack and Fly/Render/Vercel deployment configuration. | Preserve unless a separate owner request changes hosted-product scope. |

## Module classification

| Area | Classification | Current responsibility and coupling |
|---|---|---|
| main.py | Mixed runtime, tools, audio, and desktop bootstrap | 2,343 lines. Owns Gemini Live setup, declarations and dispatch, state, audio, preferences, approvals, and desktop launch. ArgusLive stores the injected client as both client and compatibility alias ui. |
| core/ | Mostly reusable core; some UI-shaped contracts | Contains ArgusClient, model selection, prompts, key validation, voice and computer-control preferences, tool approvals, and QA helpers. ArgusClient includes desktop concepts such as voice selector, theme, graphics quality, and UI commands. |
| tools/ | Tool declarations and adapter layer | Gemini-facing tool definitions wrap action implementations. ToolRegistry discovers modules and plugins. ToolContext exposes ui, speak, and speak_vision_result; tools.impl calls client methods directly for UI-specific commands. |
| actions/ | Reusable tool implementations with platform-specific integrations | Includes application launching, browser, messaging, files, web search, media, computer settings, presentations, and screen control. Some actions accept a player/UI object for logs, current file, or speech callbacks. |
| agent/ | Reusable task orchestration | Planner, executor, error handling, and task queue. Inventory import paths and side effects before separating dependencies. |
| audio/ and actions/tts_engine.py | Voice and audio runtime | Audio interface has sounddevice and dummy backends. The current desktop engine imports sounddevice directly; audio is not yet an optional installation extra. |
| ui/ | Desktop presentation | 39 Python files using PyQt6, including windows, HUD, overlays, compact mode, logs, conversation, notifications, and first-run intro. |
| api/ and web/ | Hosted service and browser presentation | FastAPI/WebSocket, authentication, Postgres/Redis, and Next.js. Kept outside the desktop-retirement scope by the decision above. |
| config/, memory/, observability/ | Shared configuration and state services | Settings, API keys, local memory/task history, logging, and metrics. Review persistence paths before introducing CLI sessions. |
| awareness/ | Mixed background service and desktop notifications | Background thread is used; it imports a popup type from ui, so that notification path needs an adapter or must be excluded from headless core imports. |
| plugins/ | Extension points | Plugins register declarations and executors into ToolRegistry. Preserve discovery and enabled-plugin behavior. |

### Existing client seam

core/argus_client.py already defines a transport-neutral ArgusClient Protocol, and api/websocket_client.py implements a hosted adapter. This is a useful extraction seam. It is incomplete for CLI use: some methods and properties represent desktop preferences or presentation state, while tools.impl and runtime code still use the client as a UI/player object. The migration should narrow or adapt the contract without changing existing API event behavior.

## Voice, tools, computer control, and search

| Capability | Current implementation | CLI boundary/risk |
|---|---|---|
| Voice input/output | main.py owns Gemini Live sessions and imports sounddevice. audio/ defines a sounddevice backend and a dummy backend; actions/tts_engine.py provides separate optional TTS integrations. | Audio imports and startup currently happen through the desktop runtime. Make voice an optional extra and keep text CLI independent of microphone/device initialization. |
| Event loops and threads | The desktop starts the async ArgusLive.run loop in a daemon thread via asyncio.run. UI callbacks use run_coroutine_threadsafe; sounddevice callbacks also have their own thread-safety requirements. | Define one CLI-owned event-loop lifecycle and cancellation path; do not start a nested loop or write over the active prompt from audio callbacks. |
| Tool definitions and execution | The Gemini Live runtime in main.py owns a static declaration set and a large dispatch path. tools/ also has declarations, ToolRegistry, and tools.impl adapters, including plugin discovery. | These are parallel paths today. Inventory parity and caller usage before consolidating; do not remove actions or plugins based only on the static CLI plan. |
| Opening applications | actions/open_app.py maps common applications to platform-specific launch commands. ScreenAgent can infer a target window and bring it forward. | Preserve aliases and platform behavior; report unavailable apps instead of selecting an unrelated target. |
| Direct mouse/keyboard | actions/computer_control.py and actions/screen_control/ use PyAutoGUI and platform-specific helpers. Direct computer control defaults to enabled in core/computer_control_preferences.py, but main.py also applies ToolApprovalManager checks to high-impact operations. | Remove per-step approvals for a clear user order. Keep a narrowly scoped confirmation for sharing a file detected as sensitive; ask a clarification only when the target is materially ambiguous. |
| Goal-oriented screen agent | actions/screen_control/ contains capture, Windows accessibility, window focus, action schemas/execution, Gemini vision, bounded observe-decide-act-verify, timeout/step limits, kill switch, and debug screenshot handling. The active-window guard rejects ARGUS's own window; Windows has an accessibility implementation. | Keep the bounded loop and focus guard. The terminal must be excluded as a target. Test with fakes; never run real mouse/keyboard or audio in automated CI. |
| Sensitive-file sharing | ScreenAgent checks explicit share requests and visible/explicit file names; safety.py recognizes .env, Docker files, credentials, secret content, and private keys. | Preserve this as the only confirmation gate for an already-authorized action; never include secret contents in the prompt or logs. |
| Anti-bot challenge | The screen agent already detects common verification text and returns without issuing another action. Browser-control code has an additional challenge check. | Preserve the immediate stop and user-facing explanation. Never solve, retry around, or route traffic to bypass a challenge. |
| Online search | actions/web_search.py on commit 146677e uses Gemini Google Search grounding, extracts cited URLs, retries one unavailable configured model, and has no direct search-engine scraping fallback. main.py still describes a DDG fallback in its tool declaration. | Align the declaration with actual behavior; ordinary research should not open a browser or scrape search-engine result pages. Browser automation is reserved for explicit visible-browser requests. |
| Logs and persisted state | The runtime writes client-facing logs/subtitles; observability/ contains logging/metrics; memory/ contains local memory/config and task-history facilities. Screen screenshots are saved only when the explicit debug option is enabled. | Add CLI session storage separately from long-term memory, set a retention/deletion policy, and keep screenshots out of the database by default. |

### Confirmation-policy mismatch to resolve in implementation

core/tool_approval.py and main.py currently implement turn-bound approvals for some high-impact tools and drafts. That behavior does not match the owner's instruction that a direct user request authorizes completion. For this migration, preserve only a sensitive-file-share confirmation and genuine clarification of an ambiguous target; do not add general ask/safe/never prompts or a confirmation before each mouse, keyboard, or message action.

## Packaging, tests, CI, documentation, and platform support

### Packaging and installation

- pyproject.toml uses setuptools and exposes the argus command, but package discovery currently includes ui and project metadata describes a desktop assistant.
- requirements.txt aggregates requirements-desktop.txt and requirements-api.txt. The desktop profile includes PyQt6, sounddevice, PyAutoGUI, screen capture, browser, file, presentation, and optional TTS libraries. The API profile still includes sounddevice and the legacy Gemini SDK because current import paths need them.
- ARGUS.spec and ARGUS-Debug.spec are PyInstaller desktop builds; both package assets/fonts, and the release build includes UI hidden imports.
- scripts/create_locked_dmg.sh builds a macOS desktop image. setup_argus.py, setup_argus.bat, setup_argus.sh, start_argus.bat, start_argus.sh, and start_argus.command install or launch from a local clone and .venv.
- scripts/install_argus_cli.sh only links scripts/argus into a user bin directory; it does not install an independent CLI package.
- Docker, docker-compose.yml, alembic/, Fly/Render manifests, and the manual deployment workflow belong to the hosted API/web service and should remain.

### Tests and continuous integration

- tests/ contains Python tests for actions, API, providers, tool contracts, screen control, security, and desktop UI. Some suites import PyQt or platform-specific libraries.
- .github/workflows/ci.yml has an Ubuntu backend job with Postgres and Redis, Xvfb, and the complete Python pytest suite, plus an Ubuntu Node job for web install, typecheck, lint, and build.
- The CI workflow has no Windows/macOS runner matrix and does not build/install a wheel. A Linux-green run is not proof of real Windows/macOS screen control, audio permissions, or package installation.
- docs/QA.md separates safe automated checks from supervised hardware and desktop checks. Real mouse/keyboard/audio should stay mocked in normal CI; owner verification remains necessary for live desktop permissions, audio, and a clean-machine install.

### Platform and documentation claims

- README.md claims Windows, macOS, and Linux support for the local product. actions/open_app.py contains platform-specific application aliases; advanced window focus and accessibility code currently includes Windows APIs.
- The current CI only runs backend and frontend on Ubuntu. The platform support matrix must be measured per capability, not inferred from the README claim.
- Relevant documentation includes README.md, docs/USAGE.md, docs/TERMS.md, docs/QA.md, docs/ARCHITECTURE.md, docs/TUTORIAL.md, docs/OPENJARVIS_COMPARISON.md, and docs/ui/.
- Some existing docs are stale snapshots: docs/ARCHITECTURE.md describes a historical ui.py layout while the current code is a ui/ package; README.md still shows an old anonymandk/argus clone URL. Migration docs should update those references without changing hosted API/web deployment instructions.
