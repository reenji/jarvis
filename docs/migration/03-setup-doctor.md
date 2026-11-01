# Phase 3: setup, configuration, and doctor

## Setup and config

`argus setup` is interactive. It skips the hidden API-key prompt when an
environment, user-config, keyring, or legacy key is already available, then
validates the selected key with one small Gemini text request capped at a
10-second client timeout. Provider error messages are mapped to short
credential, quota, server, or network hints; raw SDK exception text and key
values are never printed. The prompt uses `getpass` so newly entered keys are
not echoed. Setup asks whether optional voice should be enabled and saves the
preference. When voice is enabled, `argus` without a subcommand starts voice
mode; `argus chat` always selects text mode. `argus voice` explicitly starts
voice mode regardless of the saved default.

When a secure system keyring backend is available, setup stores the Gemini key
there and writes only a keyring reference in the config. Otherwise it stores
the key in the user config file and applies owner-only POSIX permissions. On
Windows, the file inherits the user's profile ACL. It writes atomically and
does not put user settings in the repository. The config path defaults to the
same per-user state directory as the session database; `ARGUS_CONFIG_FILE`
overrides it and `ARGUS_HOME` selects the shared per-user directory.

Commands:

- `argus config path` prints the user config path.
- `argus config show` prints the effective model and voice settings while
  redacting the API key.
- `argus config set voice.enabled true|false` and `argus config set voice.name
  <name>` change voice preferences. The saved voice name is used by the CLI's
  Live session.
- `argus config set llm.model <model>` selects the text model. The
  `ARGUS_CLI_MODEL` environment variable takes precedence.

`argus config set` rejects API-key fields. Use `argus setup` for the hidden
prompt instead of putting a key in shell history.

## Doctor checks

`argus doctor` reports ARGUS and Python versions, config readability, Gemini
key and API access, SQLite write access, screen capture, mouse/keyboard tooling,
audio devices when the audio dependency is installed, and terminal encoding,
color, and dimensions. Critical failures are Python version, malformed config,
missing or unusable API access, and unwritable SQLite storage; these produce a
nonzero exit status with a correction hint.

The screen probe captures one frame in memory and does not save it. The input
probe only reads the current pointer position; it never clicks or types. This
confirms the desktop toolkit is reachable but cannot prove that the operating
system will permit a future input event. macOS Accessibility permissions and
Wayland limitations are described in the diagnostic. Audio checks only list
devices and never open a microphone or speaker stream.

Automated tests use mocked API and hardware clients. They do not make a live
Gemini request or send real mouse, keyboard, screen, or audio operations. The
base package supplies local computer-control dependencies; missing optional
browser, document, or audio packages are reported as unavailable capabilities.
See [Phase 6 packaging](06-packaging.md) for install profiles and repair steps.
