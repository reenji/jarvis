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

## Change and branch policy

- Every feature/change is isolated in its own feat/slug branch and PR with exactly five meaningful commits.
- Every bug fix uses bugfix/slug and exactly three meaningful commits.
- When a PR depends on an unmerged PR, stack it on that PR's branch so its diff contains only its own change. Do not merge or push directly to main.

## Release marker

Create app-final at the last commit that still contains the desktop app, immediately before the dedicated desktop-retirement change. Do not tag an intermediate inventory or CLI-foundation commit.
