Thank you for considering contributing!

- Fork the repository and open a pull request.
- Keep changes focused and small; one feature or fix per PR.
- Update `README.md` or docs for any user-visible changes.

## Repository hygiene

Remove local backup files such as `*.bak` before committing. Git ignores these files automatically.

## Python checks

Use Python 3.11 or newer. Install the complete development profile from the
repository root:

```bash
python -m pip install -r requirements-dev.txt
```

Run the full Python suite in Qt's headless mode and keep test-created files in
an isolated workspace:

```bash
export QT_QPA_PLATFORM=offscreen
export ARGUS_QA_MODE=1
export ARGUS_QA_WORKSPACE="$PWD/.qa-artifacts/local"
mkdir -p "$ARGUS_QA_WORKSPACE"
python -m pytest -q tests
python scripts/qa.py automated
```

`scripts/qa.py automated` also checks source compilation, installed dependency
consistency, UI-token contrast, offscreen UI evidence, and tracked secrets. It
writes reports and captures below `.qa-artifacts/`. The QA workspace is for
automated fixtures; live messages, computer control, real Gemini sessions, and
other external effects are not part of this check.

PowerShell equivalent for the same environment:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:ARGUS_QA_MODE = "1"
$env:ARGUS_QA_WORKSPACE = Join-Path $PWD ".qa-artifacts/local"
New-Item -ItemType Directory -Force $env:ARGUS_QA_WORKSPACE | Out-Null
python -m pytest -q tests
python scripts/qa.py automated
```

## Web checks and screenshots

The web client requires Node.js 24, as used by CI. From `web/`, install the
locked dependencies and run every configured check:

```bash
npm ci
npm run typecheck
npm run lint
npm run build
```

To regenerate the deterministic Playwright UI evidence, first complete the
production build, then from the repository root run:

```bash
python -m playwright install chromium
python scripts/capture_web_ui.py
```

The capture script serves the production build and uses synthetic API and
WebSocket fixtures. It captures authentication, onboarding, all seven visible
session states, a populated console, and reduced motion under
`docs/ui/evidence/f5/`. It checks horizontal overflow and verifies the compact
viewport and reduced-motion scrolling behavior. These captures do not prove
live API or Gemini interoperability.

Desktop reference captures are indexed in
[`docs/ui/evidence/f4/README.md`](docs/ui/evidence/f4/README.md); they are
generated through the offscreen Qt probe with isolated settings paths.

Before committing, scan staged changes for secrets:

```bash
scripts/pre-commit-check.sh
```

If you find an accidental secret, notify the maintainers immediately and do
not share the secret in public.
