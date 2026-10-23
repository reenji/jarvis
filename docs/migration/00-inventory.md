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
