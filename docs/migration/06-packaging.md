# Phase 6: packaging and installation

ARGUS installs from the GitHub repository; it is not published to PyPI. The
package requires Python 3.11 or newer and registers the `argus` command.

## Install

On macOS or Linux, from a repository checkout:

```bash
./scripts/install.sh
```

On Windows PowerShell:

```powershell
.\scripts\install.ps1
```

Both scripts check for a supported Python version, use `uv` when available or
fall back to `pipx`, install ARGUS from GitHub, and run `argus setup`. They do
not remove existing files, settings, or sessions. Install `uv` or `pipx` from
its official source before running the script if neither is already available.

The scripts install the local computer-control dependencies. Voice stays
optional; pass `--voice` on macOS/Linux or `-Voice` on Windows to install its
microphone and speaker dependencies too:

```bash
./scripts/install.sh --voice
```

```powershell
.\scripts\install.ps1 -Voice
```

You can also install directly with either tool:

```bash
pipx install git+https://github.com/reenji/jarvis.git
uv tool install git+https://github.com/reenji/jarvis.git
```

To include voice, use the package extra with the same tool. For example:

```bash
pipx install --force 'argus-mark-xxxix[voice] @ git+https://github.com/reenji/jarvis.git'
uv tool install 'argus-mark-xxxix[voice] @ git+https://github.com/reenji/jarvis.git'
```

After installation, `argus setup` securely configures Gemini and `argus doctor`
checks the local installation. Without an API key, `doctor` still runs its
local checks and exits nonzero with a configuration hint; it makes no Gemini
request in that case.

## Dependency profiles

The base install includes the text CLI, Gemini text SDK, Rich terminal output,
terminal/configuration support, and the local screen, mouse, keyboard, and app-focus packages used by
the CLI's computer tools. Windows-only accessibility and audio-control
libraries use platform markers. PyQt is not a base dependency.

Optional extras keep less common integrations out of a normal install:

- `voice`: NumPy and `sounddevice` for Gemini Live audio.
- `browser`: Playwright and web-page parsing support.
- `documents`: Office, PDF, spreadsheet, and file-conversion tools.
- `integrations`: Google service and YouTube connectors.
- `tts`: additional speech providers.
- `api`: hosted FastAPI, database, and cache runtime dependencies.

The API deployment remains on its existing `requirements-api.txt` profile.
`requirements.txt`, Docker, database migrations, deployment manifests, and the
hosted API/web CI jobs remain in place during the CLI migration.

## Package verification

The packaging CI job builds a wheel, installs it with its base dependencies in
a clean virtual environment, and runs `argus --version` and `argus doctor`.
The doctor smoke check uses a fresh temporary `ARGUS_HOME` and no API key, so
it does not contact Gemini or access user settings.
