# ARGUS

Local Gemini Live desktop assistant with a PyQt6 interface, voice interaction, detachable panels, and optional browser, file, screen, and messaging tools.

ARGUS is the product name; its source repository is [`reenji/jarvis`](https://github.com/reenji/jarvis).

ARGUS also includes a dedicated presentation studio that creates, edits,
redesigns, and extends editable widescreen `.pptx` decks from documents, data,
images, audio, and video, with optional PDF export. See the
[usage guide](docs/USAGE.md#6-powerpoint-presentations) for examples.

## Requirements

You need **Python 3.11 or newer** installed to set up and run ARGUS. Confirm
your Python version before continuing:

```bash
python --version
```

`requirements.txt` installs the complete desktop and hosted-API runtime for
existing setup scripts. Use `requirements-desktop.txt` or `requirements-api.txt`
for a focused runtime install, and `requirements-dev.txt` for the full test and
QA environment.

## Quick start (Windows, macOS, Linux)

In Terminal, run:

```bash
git clone https://github.com/reenji/jarvis.git
cd jarvis
python scripts/setup_argus.py
```

On Windows, you can double-click `scripts/setup_argus.bat` instead.

Open `.env`, add your `GEMINI_API_KEY`, then launch ARGUS:

```bash
argus
```

You only need to run setup once. Activate `.venv` when opening a new terminal,
then type `argus`.

ARGUS's core UI, Gemini connection, presentations, research, files, and CLI are
cross-platform. Some computer-control, email, media, and browser integrations
depend on permissions and available applications on each operating system.
Direct mouse and keyboard control is enabled by default so ARGUS can complete
requested tasks without asking for approval for each click or keystroke. You can
disable it in **Settings → Actions**. Read the [computer-control terms](docs/TERMS.md).

O ARGUS pode abrir aplicativos pelo nome e executar tarefas visuais neles. Em
pedidos com vários passos, ele abre ou foca o aplicativo, interage com seus
controles e verifica o resultado; veja a [comparação com OpenJarvis](docs/OPENJARVIS_COMPARISON.md).

## Local document knowledge

ARGUS can index a specific document or folder you name, then search it with
file and line citations. For example, ask ARGUS to “index the folder
`C:\\Users\\Meins\\Documents\\Project`” and then ask questions about those
documents. Supported formats include text, Markdown, code, PDF, DOCX, and
PPTX. Hidden files, likely credentials, and configuration files are skipped.
The SQLite index stays under `memory/`; only short search excerpts are included
in the active model conversation, which currently uses Gemini Live. See
[the OpenJarvis comparison](docs/OPENJARVIS_COMPARISON.md) for scope and limits.

## Interface previews

The desktop and web captures below come from the repository's UI evidence. The
state, account, and connection details in these screenshots use deterministic
test fixtures; they show presentation states, not a live Gemini session.

### Desktop

![ARGUS desktop workspace with an active conversation](docs/ui/evidence/f4/screenshots/desktop/conversation-populated.png)

### Web

![ARGUS web console at the minimum desktop viewport](docs/ui/evidence/f5/screenshots/populated-980x680.png)

More captures: [desktop states and compact window](docs/ui/evidence/f4/README.md),
[web states, authentication, onboarding, and reduced motion](docs/ui/evidence/f5/README.md),
and the [UI specification and design decisions](docs/ui/README.md).

## Hosted web application

The repository also contains a multi-user FastAPI service and a Next.js web
client. Hosted sessions use Postgres for user-scoped memory and configuration,
Redis for request quotas, encrypted per-user Gemini keys, and Gemini Live over
an authenticated WebSocket. The desktop launcher continues to use its local
stores and full local action inventory.

Start the complete local web stack with Docker:

```bash
docker compose up --build
```

Then open `http://localhost:3000`. To run each service directly:

```bash
# API
cp .env.example .env
python3 -m pip install -r requirements-api.txt
alembic upgrade head
uvicorn api.server:app --reload

# Web client
cd web
cp .env.example .env.local
npm install
npm run dev
```

Production templates are included for Fly.io (`fly.toml`), Render
(`render.yaml`), and Vercel (`web/vercel.json`). Configure `DATABASE_URL`,
`REDIS_URL`, `JWT_SECRET`, `ARGUS_ENCRYPTION_KEY`, and `CORS_ORIGINS` on the
API host. Configure `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` on Vercel.
The deployment workflow runs manually after the Fly and Vercel repository
secrets have been added.

## Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
cp .env.example .env
./scripts/install_argus_cli.sh
argus
```

Set `GEMINI_API_KEY` in `.env` before launch. Optional settings such as voice and local API keys are documented in `.env.example`.

### Launch with `argus`

The CLI launcher is included in this repository. After cloning and completing
the one-time setup, install it for your user with:

```bash
./scripts/install_argus_cli.sh
```

Open a new terminal (or reload your shell profile), then start ARGUS with:

```bash
argus
```

Before packaging or releasing the desktop app, run the side-effect-safe
capability audit:

```bash
argus --self-test
```

The audit exercises voice/tool contracts, messaging routing and approval
boundaries, a local browser interaction, isolated file operations, vision,
agent recovery, and memory. It never sends a real message or performs a live
desktop mutation. Results that still require a person, account, or physical
device are labeled `LIVE CHECK REQUIRED`, and a JSON report is written under
`.qa-artifacts/`.

Alternatively, from an activated virtual environment, `python3 -m pip install -e .`
installs the same `argus` command through the standard Python package entry point.

## Documentation

- [Usage guide](docs/USAGE.md)
- [Tutorial](docs/TUTORIAL.md)
- [Complete QA and bug-audit guide](docs/QA.md)
- [UI specification, decisions, and screenshots](docs/ui/README.md)
- [Contribution notes](CONTRIBUTING.md)

## Configuration files

Template files are included for local setup:

- `.env.example`
- `config/api_keys.example.json`
- `config/layout_settings.example.json`
- `config/ui_settings.example.json`
- `memory/long_term.example.json`
- `memory/task_history.example.json`

## Publishing checklist

- Keep `.env` and local secret files out of git.
- Do not commit `memory/long_term.json` or `config/api_keys.json`.
- Run `python3 -m compileall -q main.py ui actions core api` before tagging a release.

## License

MIT License, see [LICENSE](LICENSE).
