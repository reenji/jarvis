# Phase 2: text CLI and sessions

The `argus` console script now points to `cli.app:main`. With no subcommand it
starts an interactive text conversation; `argus chat` does the same explicitly.
`argus ask <prompt>` sends one turn and prints the response. The one-shot form
also prints the session ID to stderr so it can be resumed later.

## Commands

- `argus chat [--session ID]` starts a new session or resumes an existing one.
- `argus ask <prompt> [--session ID]` sends one turn, optionally appending it to
  a session.
- `argus sessions [--limit N]` lists recent sessions.
- `argus delete ID` deletes a session. A unique ID prefix is accepted.
- Interactive slash commands: `/help`, `/new`, `/sessions`, `/doctor`,
  `/resume ID`, `/clear`, `/delete ID`, and `/exit`.

The CLI sends normal text requests to Gemini and handles function calls through
the existing tool registry. It keeps the model's function-call content in the
conversation history, executes each declared call through the registry, and
returns the matching function response. A turn stops after eight consecutive
tool rounds. UI-only tools for theme, graphics quality, and window control are
not offered in a terminal session.

## Local session history

Conversation history is separate from ARGUS long-term memory and is stored in
SQLite under the current user's state directory:

- Windows: `%LOCALAPPDATA%\Argus\sessions.sqlite3`
- macOS: `~/Library/Application Support/Argus/sessions.sqlite3`
- Linux: `$XDG_STATE_HOME/argus/sessions.sqlite3`, or
  `~/.local/state/argus/sessions.sqlite3`

`ARGUS_SESSION_DB` overrides the database file path; `ARGUS_HOME` overrides its
parent state directory. Sessions older than 30 days are removed when the store
opens. Set `ARGUS_SESSION_RETENTION_DAYS=0` to disable automatic expiration.
The application requests owner-only directory and file permissions on systems
that support POSIX modes. On Windows it relies on the user's profile ACL.
Deleting a session removes its stored history from the database.

The CLI imports the Google client and tool registry only when starting a
conversation. Listing and deleting saved sessions do not initialize Gemini or
audio devices. Audio remains outside this phase and is not needed for text mode.
The package dependency and installer split is handled in Phase 6; until then,
use the repository's established environment setup to supply runtime packages.

## Remaining Phase 2 parity work

This first pass provides usable text sessions but does not yet meet every PDF
acceptance criterion. Before Phase 7, add the eye banner and brand candidates,
Rich streaming and tool/source lines, `-q` and `--continue` aliases, prompt
history and slash completion, and clean Ctrl+C cancellation of an in-progress
tool action. Track these as a separate feature change rather than treating this
phase as complete.
