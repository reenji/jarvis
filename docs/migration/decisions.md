# Migration decisions

These decisions adapt the attached migration plan to reenji/jarvis and the owner's instructions. Revisit an item only if repository evidence or the owner changes its scope.

## Scope

- Replace the local PyQt desktop launcher with a terminal CLI.
- Preserve the independently deployable FastAPI service, Next.js client, database migrations, Docker setup, and their CI/deploy workflows. The migration request targets the desktop app; the PDF does not explicitly ask to retire the hosted product.
- Preserve current Python runtime behavior and integrations while extracting them behind CLI-friendly interfaces; do not rewrite the agent or prompts as part of the transport change.

## User authorization and safety

- A direct user instruction authorizes the requested computer action, including mouse/keyboard use and sending the requested message. Do not ask the user to click, select, or approve each step.
- Ask before sharing a file only when it appears to contain harmful-to-share material such as .env, Docker configuration, credentials, tokens, or private keys. Never reveal secret values in the prompt.
- Keep the anti-bot rule: stop automation when a verification challenge appears; do not solve or bypass it.
- Do not persist screenshots by default. Any diagnostic screenshot saving must be explicit and local.

### Phase 4: screen control

- Screen focus, active-window metadata, and screen control use the existing Win32 backend. `argus doctor` reports this capability as unavailable on non-Windows systems rather than treating a readable pointer position as proof that the full flow works. App launching and text-only CLI use remain independent.
- Bound each visual run by action and elapsed-time limits. Keep the emergency stop hotkey active and protect the ARGUS terminal from becoming a screen-control target.
- Apply a short configurable wait after focusing or launching an app so its window can settle before the first capture.
- A direct user order is sufficient for ordinary UI actions. Ask only before sharing a file identified as credentials, environment configuration, Docker configuration, or another sensitive artifact. Opening such a file is not itself a share request.
- When an anti-bot challenge appears, stop before interacting. The CLI can wait for the user to resolve it manually and resume the original task once; a challenge that remains visible ends the run.
- Diagnostic screen images stay disabled by default. When explicitly enabled with `--debug-screens` or `ARGUS_DEBUG_SCREENSHOTS`, store them under the per-user ARGUS debug directory, separated by run ID.

### Phase 5: optional voice

- Keep the text CLI independent of audio libraries. Import the desktop live engine and audio runtime only after `argus voice` is selected or the saved `voice.enabled` preference selects voice as the default.
- An explicit `argus chat` always starts text mode, including when voice is the saved default. The explicit `argus voice` command starts voice mode directly.
- Reuse Gemini Live and its existing tool execution path through a terminal adapter; do not start the PyQt desktop UI. Show completed user and assistant transcripts in the terminal without printing partial transcription fragments as separate lines.
- Voice mode uses the user's existing Gemini setup and saved voice name; its audio dependencies remain optional and are packaged in Phase 6.
- If the optional voice dependency or a usable microphone/speaker is unavailable, explain the limitation and continue in an interactive text session. Check device availability without opening audio streams. Provider configuration or network failures remain voice errors and do not silently switch modes.

## Configuration storage

- Store the user config next to the CLI's per-user state database, using the OS-specific directory already selected by `ARGUS_HOME` and the session store. This keeps config, session state, and their access controls together; `ARGUS_CONFIG_FILE` can select a different config file.
- Alternatives considered: always use `~/.argus/config.yaml`, or follow the standard OS config directory separately from session state. The OS-specific state path was chosen to match Phase 2, avoid a second per-user directory, and use the Windows profile ACL. POSIX directories and config files are restricted to owner access.
- Prefer a system keyring backend when it is available and secure; otherwise store the API key in the restricted config file. `argus config show` never prints the key, and `argus config set` refuses secret fields so they do not enter shell history.

## Change and branch policy

- Every feature/change is isolated in its own feat/slug branch and PR with exactly five meaningful commits.
- Every bug fix uses bugfix/slug and exactly three meaningful commits.
- When a PR depends on an unmerged PR, stack it on that PR's branch so its diff contains only its own change. Do not merge or push directly to main.

## Release marker

Create app-final at the last commit that still contains the desktop app, immediately before the dedicated desktop-retirement change. Do not tag an intermediate inventory or CLI-foundation commit.
