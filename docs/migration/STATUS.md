# CLI migration status

Repository: reenji/jarvis
Execution branch: feat/cli-inventory
Migration plan source: attached PDF, reviewed before implementation.

## Progress

| Phase | Status | Notes |
|---|---|---|
| 0. Repository inventory | In progress | Documentation only; no runtime code changed. |
| 1. Core boundaries | Pending | Preserve existing desktop and hosted adapters until the CLI works. |
| 2. Text CLI and sessions | Pending | The existing argus entry point currently starts the desktop UI. |
| 3. Setup, configuration, and doctor | Pending | Keep secrets out of the repository and terminal output. |
| 4. Desktop tools | Pending | Preserve direct user commands; stop on anti-bot challenges. |
| 5. Optional voice | Pending | Text mode must remain available without audio dependencies. |
| 6. Packaging and installation | Pending | Keep the hosted API/web deployment path intact. |
| 7. Retire the desktop app | Pending | Only after the replacement CLI is usable and verified. |
| 8. Final tests, CI, and documentation | Pending | Move the pre-removal CI/test gate ahead of phase 7. |

## Execution rules

- One pull request per coherent change.
- Each feature pull request contains exactly five meaningful commits.
- Each bug-fix pull request contains exactly three meaningful commits.
- Feature branches use feat/slug; bug-fix branches use bugfix/slug.
- Dependent pull requests may be stacked on the preceding open branch, with the base recorded in each PR.
- Do not create the app-final tag until the last commit containing the desktop app is known and the removal phase is ready.
