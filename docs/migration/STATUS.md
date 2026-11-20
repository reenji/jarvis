# CLI migration status

Repository: reenji/jarvis
Active branch: main (all CLI migration branches are merged)
Current release: v0.3.0 (Windows, macOS and Linux desktop builds plus the `argus` CLI)
Migration plan source: attached PDF, reviewed before implementation.

## Progress

| Phase | Status | Notes |
|---|---|---|
| 0. Repository inventory | Complete | Documentation only; no runtime code changed. |
| 1. Core boundaries | Complete | Split required conversation events from optional desktop controls; keep adapter compatibility. |
| 2. Text CLI and sessions | Complete | Adds ASCII eye branding with visibility controls, Rich streaming, tool lines, `-q`/`--continue`/`--resume`, `--voice`/`/voice`, private prompt history, slash completion, and clean cancellation/exit behavior. Focused CLI tests pass; the full pre-removal suite remains pending. |
| 3. Setup, configuration, and doctor | Implemented | Adds hidden-key setup, private user config, redacted config commands, and local/API diagnostics. Clean-install verification depends on Phase 6 packaging. PR is stacked on Phase 2. |
| 4. Desktop tools | Implemented; desktop validation pending | Bounded Windows screen control, terminal protection, app focus delay, sensitive-share guard, anti-bot stop, and opt-in local debug screenshots. |
| 5. Optional voice | Implemented; live hardware validation pending | Adds Gemini Live terminal mode, saved default-mode preference, full-turn transcripts, lazy audio loading, and text fallback when audio support or devices are unavailable. |
| 6. Packaging and installation | Complete | Adds dependency extras, GitHub-based pipx/uv installers for macOS/Linux and Windows, and an isolated wheel smoke check. Keeps hosted API/web manifests and deployment workflows. |
| 7. Retire the desktop app | Dropped | The owner decided on 2026-10-31 that the desktop app is the ARGUS product; it ships next to the CLI. |
| 8. Final tests, CI, and documentation | In progress | Full suite and the cli-package gate run in hosted CI; manual desktop and voice validation remain. |

## Execution rules

- One pull request per coherent change.
- Each feature pull request contains exactly five meaningful commits.
- Each bug-fix pull request contains exactly three meaningful commits.
- Feature branches use feat/slug; bug-fix branches use bugfix/slug.
- Branch every pull request from main. Stacked PRs #24–#46 were merged into their base branches and never reached main.
- Check that a pull request is still open before pushing more commits to its branch.

## Current state

Phases 0–6 are merged into main. The desktop app stays: `.github/workflows/release.yml` builds the Windows installer and portable zip, the macOS disk image and the Linux .deb and tarball from each `v*` tag, and the same install provides the `argus` CLI.

Still open:

- Phase 4: screen control checked on a real Windows desktop.
- Phase 5: voice mode checked with a real microphone and speaker.
- The hidden child consoles from #58, which only show on real Windows.
