# Phase 1: core and adapter boundary

This phase makes the existing live engine depend on conversation events instead
of requiring every connected client to behave like the desktop window.

## Contracts

- `core.argus_client.ArgusClient` contains the events needed by a conversation
  client: text-command callback, log output, status, and transcript output.
- `ArgusDesktopClient` describes the additional desktop controls: mute and
  selected-file state, voice selector, themes, graphics quality, and window
  commands. These controls are not required for a terminal adapter.
- `ArgusLive` uses its injected `client` for engine events and tool dispatch.
  It keeps the historical `ui` attribute as a compatibility alias for existing
  integrations. Optional desktop controls are checked at the call site and
  report when they are unavailable.
- `ToolContext` exposes `client` to tool implementations. Its `ui` property and
  the `ui=` constructor keyword remain compatibility aliases for plugins still
  using the previous shape.

The desktop `ArgusUI` and hosted `WebSocketClient` continue to provide the
existing conversation events and keep their current behavior. No hosted event
names or payloads change in this phase.

## Follow-up boundary work

`ArgusLive` still lives in `main.py`, which imports audio and provider
dependencies at module load. This phase does not make a text-only install
possible by itself. Phase 2 must extract or adapt the runtime lifecycle and
defer microphone initialization so the CLI can start without desktop audio.
Tools that use optional selected-file or mute state must continue to treat
those values as adapter-provided context.

## Verification

`tests/test_phase1_decoupling.py` covers the base and desktop contracts, a
headless client, graceful handling of unavailable visual controls, and the
`ToolContext` compatibility aliases. The focused suite passed on Windows with
temporary test dependencies; it does not exercise live audio or real desktop
input.
