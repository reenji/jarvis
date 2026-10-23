import asyncio
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from google.genai import types

from cli.app import build_parser, main
from cli.history import SessionStore
from cli.conversation import TextConversation


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "state" / "sessions.sqlite3"
        self.store = SessionStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_session_history_can_be_resumed_cleared_and_deleted(self):
        session_id = self.store.create("Spotify task")
        history = [{"role": "user", "parts": [{"text": "play music"}]}]
        self.store.save_history(session_id, history)

        self.assertEqual(self.store.resolve(session_id[:10]), session_id)
        self.assertEqual(self.store.load_history(session_id), history)
        self.store.clear(session_id)
        self.assertEqual(self.store.load_history(session_id), [])
        self.assertTrue(self.store.delete(session_id))
        self.assertIsNone(self.store.resolve(session_id))

    def test_expired_sessions_are_removed_on_store_open(self):
        session_id = self.store.create("Old chat")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00+00:00", session_id),
            )
            connection.commit()
        finally:
            connection.close()

        reopened = SessionStore(self.db_path, retention_days=30)

        self.assertEqual(reopened.list(), [])

    def test_parser_supports_single_turn_interactive_and_history_commands(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["ask", "hello", "Argus"]).prompt, ["hello", "Argus"])
        self.assertEqual(parser.parse_args(["chat", "--resume", "abc"]).session, "abc")
        self.assertEqual(parser.parse_args(["sessions", "--limit", "5"]).limit, 5)

    def test_sessions_command_does_not_load_model_or_audio_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            from unittest.mock import patch

            with patch.dict(os.environ, {"ARGUS_SESSION_DB": str(Path(temp_dir) / "sessions.sqlite3")}):
                self.assertEqual(main(["sessions"]), 0)


class FakeRegistry:
    def __init__(self):
        self.declarations_value = [
            {
                "name": "open_app",
                "description": "Open a local app",
                "parameters": {"type": "OBJECT", "properties": {}},
            }
        ]
        self.execute = AsyncMock(return_value={"result": "Opened Calculator."})

    def declarations(self):
        return self.declarations_value


class TextConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SessionStore(Path(self.temp_dir.name) / "sessions.sqlite3")
        self.session_id = self.store.create("Tool loop")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_text_turn_executes_tool_and_persists_restorable_history(self):
        tool_content = types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        id="call-1",
                        name="open_app",
                        args={"app_name": "Calculator"},
                    )
                )
            ],
        )
        answer_content = types.Content(
            role="model",
            parts=[types.Part(text="Calculator is open.")],
        )
        responses = [
            SimpleNamespace(candidates=[SimpleNamespace(content=tool_content)], text=None),
            SimpleNamespace(candidates=[SimpleNamespace(content=answer_content)], text="Calculator is open."),
        ]
        models = SimpleNamespace(generate_content=Mock(side_effect=responses))
        client = SimpleNamespace(models=models)
        registry = FakeRegistry()
        conversation = TextConversation(
            self.session_id,
            self.store,
            client=client,
            registry=registry,
            system_instruction="test system instruction",
        )

        answer = asyncio.run(conversation.ask("Open Calculator"))

        self.assertEqual(answer, "Calculator is open.")
        self.assertEqual(registry.execute.await_count, 1)
        self.assertEqual(registry.execute.await_args.kwargs["name"], "open_app")
        self.assertEqual(len(self.store.load_history(self.session_id)), 4)
        first_config = models.generate_content.call_args_list[0].kwargs["config"]
        self.assertTrue(first_config.automatic_function_calling.disable)
        self.assertEqual(first_config.tools[0].function_declarations[0].name, "open_app")


if __name__ == "__main__":
    unittest.main()
