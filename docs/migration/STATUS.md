# CLI migration status

Repository: reenji/jarvis
Active branch: feat/cli-voice (stacked on feat/cli-terminal-tools)
Migration plan source: attached PDF, reviewed before implementation.

## Progress

| Phase | Status | Notes |
|---|---|---|
| 0. Repository inventory | Complete | Documentation only; no runtime code changed. |
| 1. Core boundaries | Complete | Split required conversation events from optional desktop controls; keep adapter compatibility. |
| 2. Text CLI and sessions | Partial | Text turns and SQLite sessions work. A Phase 2 parity follow-up is still required for the eye banner, Rich streaming/tool output, `-q`/`--continue`, prompt history/completion, and cancellation behavior before Phase 7. |
| 3. Setup, configuration, and doctor | Implemented | Adds hidden-key setup, private user config, redacted config commands, and local/API diagnostics. Clean-install verification depends on Phase 6 packaging. PR is stacked on Phase 2. |
| 4. Desktop tools | Implemented; desktop validation pending | Bounded Windows screen control, terminal protection, app focus delay, sensitive-share guard, anti-bot stop, and opt-in local debug screenshots. |
| 5. Optional voice | Implemented; live hardware validation pending | Adds Gemini Live terminal mode, saved default-mode preference, full-turn transcripts, lazy audio loading, and text fallback when audio support or devices are unavailable. |
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

## Phase 0 result

The repository inventory and migration decisions are committed on feat/cli-inventory. Phase 0 changed documentation only; Phase 1 defines adapter boundaries and retains the desktop and hosted clients. Phase 2 has a working text CLI and resumable sessions, with the parity items above still open. Phase 3 adds setup, configuration, and doctor in its own feature PR. Phase 4 adds bounded Windows screen interaction and safety behavior; real desktop validation remains pending. Phase 5 adds optional Gemini Live voice mode; real microphone and speaker validation remains pending. Next is packaging and installation.
