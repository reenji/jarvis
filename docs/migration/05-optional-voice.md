# Phase 5: optional voice

## Voice and text entry points

`argus voice` starts the existing Gemini Live audio engine from the terminal
without opening the PyQt desktop window. It uses the Gemini key configured by
`argus setup` and the saved `voice.name` preference. Press Ctrl+C to leave the
voice session.

When `voice.enabled` is true, `argus` with no subcommand starts voice mode.
When it is false, the existing text conversation remains the default.
`argus chat` always starts text mode, even if voice is the saved default, and
`argus ask <prompt>` continues to send a one-shot text request. `argus voice`
starts voice mode directly regardless of that default preference.
If the optional audio package is absent, the platform audio backend cannot load,
or no microphone and speaker are available, ARGUS explains the problem and opens
a text session instead. The device check only lists capabilities; it does not
open an audio stream. An explicit voice command and the saved voice default use
the same fallback.

The terminal voice adapter prints completed user and assistant transcripts,
tool status, and error messages. It suppresses partial speech-transcription
fragments so the terminal stays readable. Voice uses the same Gemini Live tool
execution path and does not start a desktop window.

## Optional dependencies

Text commands do not import `sounddevice` or the live audio engine. If the
audio dependency is missing, voice mode falls back to text and identifies the
optional `voice` extra. Install it with `scripts/install.sh --voice` or
`scripts/install.ps1 -Voice`, or use the direct `pipx`/`uv` instructions in
[Phase 6 packaging](06-packaging.md). The setup prompt may save a voice
preference even when the optional runtime has not yet been installed; text
remains available until audio is installed.

Automated coverage uses a fake voice engine, fake settings and API-key
providers, and captured terminal output. It verifies explicit and default
mode selection, text-mode override, transcript rendering, optional dependency
errors, missing-device fallback, and Ctrl+C shutdown without opening a
microphone or speaker or making a Gemini Live request. A supervised microphone
and speaker check remains necessary before the desktop app can be retired.
