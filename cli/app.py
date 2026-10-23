"""ARGUS text CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from cli.history import SessionStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="argus",
        description="ARGUS text assistant. Start an interactive session or ask one question.",
    )
    parser.add_argument("--version", action="version", version="ARGUS CLI 0.1.0")
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
):
    from cli.conversation import TextConversation

    resolved = _resolve_session(store, session_id)
    if resolved is None:
        resolved = store.create(title)
    return TextConversation(resolved, store)


def _read_prompt(prompt: str) -> str:
    try:
        from prompt_toolkit import prompt as prompt_toolkit_prompt
    except ImportError:
        return input(prompt)
    return prompt_toolkit_prompt(prompt)


async def _interactive(store: SessionStore, session_id: str | None) -> int:
    try:
        conversation = _new_conversation(store, session_id)
    except (ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"ARGUS text session {conversation.session_id[:12]}. Type /help for commands.")
    while True:
        try:
            text = _read_prompt("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nARGUS session saved.")
            return 0
        if not text:
            continue
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0].casefold()
            argument = parts[1].strip() if len(parts) == 2 else ""
            if command in {"/exit", "/quit"}:
                print("ARGUS session saved.")
                return 0
            if command == "/help":
                print(
                    "/new — start a new session\n"
                    "/sessions — list saved sessions\n"
                    "/resume ID — switch to a saved session\n"
                    "/clear — clear this session's conversation\n"
                    "/delete ID — delete a saved session\n"
                    "/exit — save and leave"
                )
                continue
            if command == "/sessions":
                _show_sessions(store)
                continue
            if command == "/new":
                conversation = _new_conversation(store, None)
                print(f"Started session {conversation.session_id[:12]}.")
                continue
            if command == "/clear":
                store.clear(conversation.session_id)
                conversation = _new_conversation(store, conversation.session_id)
                print("This session's conversation was cleared.")
                continue
            if command == "/resume":
                if not argument:
                    print("Usage: /resume SESSION_ID")
                    continue
                try:
                    conversation = _new_conversation(store, argument)
                except (ValueError, KeyError) as exc:
                    print(str(exc))
                    continue
                print(f"Resumed session {conversation.session_id[:12]}.")
                continue
            if command == "/delete":
                try:
                    target_id = _resolve_session(store, argument)
                except ValueError as exc:
                    print(str(exc))
                    continue
                if target_id is None:
                    print("Usage: /delete SESSION_ID")
                    continue
                store.delete(target_id)
                if target_id == conversation.session_id:
                    conversation = _new_conversation(store, None)
                print(f"Deleted session {target_id[:12]}.")
                continue
            print(f"Unknown command: {command}. Type /help for available commands.")
            continue

        try:
            answer = await conversation.ask(text)
        except Exception as exc:
            print(f"ARGUS error: {str(exc)[:300]}", file=sys.stderr)
            continue
        print(f"ARGUS> {answer}")


async def _ask_once(store: SessionStore, prompt: str, session_id: str | None) -> int:
    try:
        conversation = _new_conversation(store, session_id, title=prompt[:120])
        answer = await conversation.ask(prompt)
    except Exception as exc:
        print(f"ARGUS error: {str(exc)[:300]}", file=sys.stderr)
        return 1
    print(answer)
    print(f"Session: {conversation.session_id}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = SessionStore()
    except OSError as exc:
        print(f"Could not open ARGUS session storage: {exc}", file=sys.stderr)
        return 2

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
        return asyncio.run(_interactive(store, getattr(args, "session", None)))
    except KeyboardInterrupt:
        print("\nARGUS session saved.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
