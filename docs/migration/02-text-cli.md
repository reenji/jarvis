# Phase 2: text CLI and sessions

The `argus` console script now points to `cli.app:main`. With no subcommand it
starts the saved default mode; `argus chat` always starts a text conversation.
Text mode shows the ARGUS eye banner, styles tool activity, and renders answers
as Markdown in a Rich panel, with a plain-text fallback for constrained output.
`argus ask <prompt>` sends one turn and prints the response. The one-shot form
also prints the session ID to stderr so it can be resumed later.

## Commands

- `argus chat [--session ID]` starts a new session or resumes an existing one.
- `argus -q <prompt>` sends one prompt without entering interactive mode.
- `argus --continue` resumes the most recently used session interactively;
  combine it with `-q` to append one turn to that session.
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

Interactive prompt history is stored in a separate `prompt-history` file next
to the session database. It is used for arrow-key recall and remains private to
the current user; slash commands are completed as they are typed.

The CLI imports the Google client and tool registry only when starting a
conversation. Listing and deleting saved sessions do not initialize Gemini or
audio devices. Audio remains outside this phase and is not needed for text mode.
The package dependency and installer split is handled in Phase 6; until then,
use the repository's established environment setup to supply runtime packages.

## Remaining Phase 2 parity work

## Phase 2 acceptance status

The terminal parity work is implemented: the eye banner, formatted and
streamed responses, tool log lines, `-q`/`--continue` shortcuts, prompt
history, slash completion, and turn cancellation. Ctrl+C during a response
cancels the active turn, removes that incomplete turn from saved conversation
history, and returns to the prompt. An SDK request or tool action that is
already running outside cancellable async code may still finish. Run the
focused CLI tests and the full pre-removal CI gate before Phase 7.
