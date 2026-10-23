"""ARGUS text CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence

from cli.history import SessionStore


class _VoiceModeRequested(Exception):
    """Signal the synchronous CLI loop to switch from text to voice."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="argus",
        description="ARGUS text assistant. Start an interactive session or ask one question.",
    )
    parser.add_argument("--version", action="version", version="ARGUS CLI 0.1.0")
    parser.add_argument(
        "-q",
        "--question",
        dest="quick_question",
        metavar="TEXT",
        help="send one prompt without entering the interactive session",
    )
    parser.add_argument(
        "--continue",
        dest="continue_session",
        action="store_true",
        help="resume the most recently used session",
    )
    parser.add_argument(
        "--resume",
        dest="resume_session",
        metavar="ID",
        help="resume a saved session by ID",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="hide the startup banner",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="start the optional live voice assistant",
    )
    parser.add_argument(
        "--debug-screens",
        action="store_true",
        help="save screen-control captures under the per-user Argus debug directory",
    )
    commands = parser.add_subparsers(dest="command")

    ask = commands.add_parser("ask", help="send one prompt and print the response")
    ask.add_argument("prompt", nargs="+", help="the question or instruction")
    ask.add_argument("--session", help="append this turn to an existing session")

    chat = commands.add_parser("chat", help="start an interactive text session")
    chat.add_argument("--session", "--resume", dest="session", help="resume an existing session")

    sessions = commands.add_parser("sessions", help="list saved sessions")
    sessions.add_argument("--limit", type=int, default=20, help="maximum number to show")

    delete = commands.add_parser("delete", help="delete a saved session")
    delete.add_argument("session_id", help="session ID or unique ID prefix")

    commands.add_parser("setup", help="configure Gemini and optional voice")
    commands.add_parser("doctor", help="check configuration and local capabilities")
    commands.add_parser("voice", help="start the optional live voice assistant")

    config = commands.add_parser("config", help="inspect or change user configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("path", help="print the user configuration path")
    config_commands.add_parser("show", help="show effective settings with secrets hidden")
    config_set = config_commands.add_parser("set", help="set a supported preference")
    config_set.add_argument("key", help="banner, voice.enabled, voice.name, or llm.model")
    config_set.add_argument("value", help="new preference value")
    return parser


def _show_sessions(store: SessionStore, *, limit: int = 20) -> None:
    sessions = store.list(limit=limit)
    if not sessions:
        print("No saved sessions.")
        return
    for session in sessions:
        print(f"{session.id[:12]}  {session.updated_at[:19]}  {session.title}")


def _resolve_session(store: SessionStore, value: str | None) -> str | None:
    if not value:
        return None
    resolved = store.resolve(value)
    if resolved is None:
        raise ValueError(f"Session not found or ID prefix is ambiguous: {value}")
    return resolved


def _new_conversation(
    store: SessionStore,
    session_id: str | None,
    *,
    title: str = "New conversation",
    terminal=None,
):
    from cli.conversation import TextConversation

    resolved = _resolve_session(store, session_id)
    if resolved is None:
        resolved = store.create(title)
    return TextConversation(resolved, store, terminal=terminal)


def _run_voice(*, show_banner: bool = True, fallback_to_text: bool = True) -> int:
    # Keep microphone and live-model imports out of every text-only command.
    from cli.voice import VOICE_UNAVAILABLE, run_voice
    if show_banner:
        from cli.terminal_ui import TerminalUI

        TerminalUI().banner()

    result = run_voice()
    if result != VOICE_UNAVAILABLE or not fallback_to_text:
        return result

    print("A voz não está disponível; iniciando uma sessão de texto.")
    try:
        store = SessionStore()
    except OSError as exc:
        print(f"Could not open ARGUS session storage: {exc}", file=sys.stderr)
        return 2
    try:
        return _run_interactive(store, None, show_banner=False)
    except KeyboardInterrupt:
        print("\nARGUS session saved.")
        return 130


def _default_voice_enabled() -> bool:
    from config.settings import get_settings

    return bool(get_settings().voice.enabled)


def _run_interactive(
    store: SessionStore,
    session_id: str | None,
    *,
    show_banner: bool = True,
) -> int:
    """Run text and voice modes sequentially on their own asyncio loops."""
    first_turn = True
    while True:
        try:
            return asyncio.run(
                _interactive(
                    store,
                    session_id,
                    show_banner=show_banner if first_turn else False,
                )
            )
        except _VoiceModeRequested:
            from cli.voice import VOICE_UNAVAILABLE

            result = _run_voice(show_banner=False, fallback_to_text=False)
            if result == VOICE_UNAVAILABLE:
                print("A voz não está disponível; continuando em texto.")
            elif result not in {0, 130}:
                return result
            first_turn = False
        except KeyboardInterrupt:
            print("\nARGUS session saved.")
            return 130


async def _interactive(
    store: SessionStore,
    session_id: str | None,
    *,
    show_banner: bool = True,
) -> int:
    from cli.client import TerminalClient
    from cli.prompt import InteractivePrompt
    from cli.terminal_ui import TerminalUI

    ui = TerminalUI()
    terminal = TerminalClient(output=ui.system, error=ui.error)
    prompter = InteractivePrompt()
    try:
        conversation = _new_conversation(store, session_id, terminal=terminal)
    except (ValueError, KeyError) as exc:
        ui.error(str(exc))
        return 2

    if show_banner:
        ui.banner()
    ui.info(f"ARGUS text session {conversation.session_id[:12]}. Type /help for commands.")
    prompt_interrupts = 0
    while True:
        try:
            text = prompter.prompt("You> ").strip()
        except EOFError:
            ui.info("\nARGUS session saved.")
            return 0
        except KeyboardInterrupt:
            prompt_interrupts += 1
            if prompt_interrupts >= 2:
                ui.info("\nARGUS session saved.")
                return 0
            ui.info("\nPress Ctrl+C again or Ctrl+D to save and exit.")
            continue
        prompt_interrupts = 0
        if not text:
            continue
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0].casefold()
            argument = parts[1].strip() if len(parts) == 2 else ""
            if command in {"/exit", "/quit"}:
                ui.info("ARGUS session saved.")
                return 0
            if command == "/help":
                ui.info(
                    "/new — start a new session\n"
                    "/sessions — list saved sessions\n"
                    "/voice — switch to voice mode, then return here\n"
                    "/doctor — check configuration and capabilities\n"
                    "/resume ID — switch to a saved session\n"
                    "/clear — clear this session's conversation\n"
                    "/delete ID — delete a saved session\n"
                    "/exit — save and leave"
                )
                continue
            if command == "/voice":
                ui.info("Switching to voice mode. Press Ctrl+C to return to text.")
                raise _VoiceModeRequested
            if command == "/sessions":
                _show_sessions(store)
                continue
            if command == "/doctor":
                from cli.doctor import run_doctor

                run_doctor()
                continue
            if command == "/new":
                conversation = _new_conversation(store, None, terminal=terminal)
                ui.info(f"Started session {conversation.session_id[:12]}.")
                continue
            if command == "/clear":
                store.clear(conversation.session_id)
                conversation = _new_conversation(store, conversation.session_id, terminal=terminal)
                ui.info("This session's conversation was cleared.")
                continue
            if command == "/resume":
                if not argument:
                    ui.info("Usage: /resume SESSION_ID")
                    continue
                try:
                    conversation = _new_conversation(store, argument, terminal=terminal)
                except (ValueError, KeyError) as exc:
                    ui.error(str(exc))
                    continue
                ui.info(f"Resumed session {conversation.session_id[:12]}.")
                continue
            if command == "/delete":
                try:
                    target_id = _resolve_session(store, argument)
                except ValueError as exc:
                    ui.error(str(exc))
                    continue
                if target_id is None:
                    ui.info("Usage: /delete SESSION_ID")
                    continue
                store.delete(target_id)
                if target_id == conversation.session_id:
                    conversation = _new_conversation(store, None, terminal=terminal)
                ui.info(f"Deleted session {target_id[:12]}.")
                continue
            ui.info(f"Unknown command: {command}. Type /help for available commands.")
            continue

        try:
            with ui.response_stream() as on_text:
                answer = await conversation.ask(text, on_text=on_text)
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None:
                task.uncancel()
            ui.info(
                "\nPedido interrompido. Uma ação que já começou pode terminar; "
                "a conversa continua."
            )
            continue
        except Exception as exc:
            ui.error(f"ARGUS error: {str(exc)[:300]}")
            continue
        ui.assistant(answer)


async def _ask_once(store: SessionStore, prompt: str, session_id: str | None) -> int:
    from cli.client import TerminalClient
    from cli.terminal_ui import TerminalUI

    ui = TerminalUI()
    terminal = TerminalClient(output=ui.system, error=ui.error)
    try:
        conversation = _new_conversation(
            store,
            session_id,
            title=prompt[:120],
            terminal=terminal,
        )
        with ui.response_stream() as on_text:
            answer = await conversation.ask(prompt, on_text=on_text)
    except Exception as exc:
        ui.error(f"ARGUS error: {str(exc)[:300]}")
        return 1
    ui.assistant(answer)
    print(f"Session: {conversation.session_id}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is not None and (
        args.quick_question is not None
        or args.continue_session
        or args.resume_session is not None
    ):
        parser.error("-q/--question, --continue, and --resume cannot be combined with a subcommand")
    if args.resume_session is not None and (args.quick_question is not None or args.continue_session):
        parser.error("--resume cannot be combined with -q/--question or --continue")
    if args.voice and (args.command is not None or args.quick_question is not None or args.continue_session):
        parser.error("--voice cannot be combined with a subcommand, -q/--question, or --continue")
    if args.quick_question is not None and not args.quick_question.strip():
        parser.error("-q/--question requires non-empty text")
    if args.debug_screens:
        os.environ["ARGUS_DEBUG_SCREENSHOTS"] = "true"
    from cli.banner import should_show_banner

    show_banner = should_show_banner(no_banner=args.no_banner)

    if args.voice:
        return _run_voice(show_banner=show_banner)

    if args.command == "setup":
        from cli.setup import run_setup

        return run_setup()
    if args.command == "doctor":
        from cli.doctor import run_doctor

        return run_doctor()
    if args.command == "voice":
        return _run_voice(show_banner=show_banner)
    if (
        args.command is None
        and args.quick_question is None
        and not args.continue_session
        and args.resume_session is None
    ):
        try:
            if _default_voice_enabled():
                return _run_voice(show_banner=show_banner)
        except (OSError, ValueError) as exc:
            print(f"Could not read the voice preference: {exc}", file=sys.stderr)
            return 2
    if args.command == "config":
        from cli.config_commands import set_config_value, show_config
        from config.user_config import user_config_path

        if args.config_command == "path":
            print(user_config_path())
            return 0
        if args.config_command == "show":
            return show_config()
        return set_config_value(args.key, args.value)

    try:
        store = SessionStore()
    except OSError as exc:
        print(f"Could not open ARGUS session storage: {exc}", file=sys.stderr)
        return 2

    if args.quick_question is not None:
        latest = store.list(limit=1) if args.continue_session else []
        session_id = latest[0].id if latest else None
        return asyncio.run(_ask_once(store, args.quick_question.strip(), session_id))
    if args.resume_session is not None:
        try:
            session_id = _resolve_session(store, args.resume_session)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return _run_interactive(store, session_id, show_banner=show_banner)
    if args.continue_session:
        latest = store.list(limit=1)
        session_id = latest[0].id if latest else None
        return _run_interactive(store, session_id, show_banner=show_banner)

    if args.command == "sessions":
        _show_sessions(store, limit=args.limit)
        return 0
    if args.command == "delete":
        try:
            session_id = _resolve_session(store, args.session_id)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if session_id is None or not store.delete(session_id):
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 2
        print(f"Deleted session {session_id[:12]}.")
        return 0

    try:
        if args.command == "ask":
            prompt = " ".join(args.prompt).strip()
            return asyncio.run(_ask_once(store, prompt, args.session))
        return _run_interactive(
            store,
            getattr(args, "session", None),
            show_banner=show_banner,
        )
    except KeyboardInterrupt:
        print("\nARGUS session saved.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
