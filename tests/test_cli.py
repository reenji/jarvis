import asyncio
from io import StringIO
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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
        self.assertEqual(parser.parse_args(["-q", "hello"]).quick_question, "hello")
        self.assertTrue(parser.parse_args(["--continue"]).continue_session)
        self.assertEqual(parser.parse_args(["sessions", "--limit", "5"]).limit, 5)
        self.assertTrue(parser.parse_args(["--debug-screens", "ask", "hello"]).debug_screens)
        self.assertEqual(parser.parse_args(["voice"]).command, "voice")

    def test_quick_question_can_append_to_the_most_recent_session(self):
        store = Mock()
        store.list.return_value = [SimpleNamespace(id="latest-session")]
        with patch("cli.app.SessionStore", return_value=store):
            with patch("cli.app._ask_once", new_callable=AsyncMock, return_value=0) as ask:
                self.assertEqual(main(["-q", "  play music  ", "--continue"]), 0)
        ask.assert_awaited_once_with(store, "play music", "latest-session")

    def test_continue_resumes_the_most_recent_session_or_starts_a_new_one(self):
        store = Mock()
        store.list.side_effect = [
            [SimpleNamespace(id="latest-session")],
            [],
        ]
        with patch("cli.app.SessionStore", return_value=store):
            with patch("cli.app._interactive", new_callable=AsyncMock, return_value=0) as chat:
                self.assertEqual(main(["--continue"]), 0)
                self.assertEqual(main(["--continue"]), 0)
        self.assertEqual(
            [call.args for call in chat.await_args_list],
            [(store, "latest-session"), (store, None)],
        )

    def test_interactive_session_continues_after_a_cancelled_turn(self):
        from contextlib import contextmanager

        from cli.app import _interactive

        class FakePrompt:
            def __init__(self):
                self.values = iter(["first request", "second request", "/exit"])

            def prompt(self, _message):
                return next(self.values)

        class FakeUI:
            def __init__(self):
                self.messages = []
                self.answers = []

            def banner(self):
                return None

            def info(self, message):
                self.messages.append(message)

            def system(self, _message):
                return None

            def error(self, _message):
                return None

            def assistant(self, answer):
                self.answers.append(answer)

            @contextmanager
            def response_stream(self):
                yield lambda _chunk: None

        class FakeConversation:
            session_id = "0123456789abcdef"

            def __init__(self):
                self.calls = 0

            async def ask(self, _text, *, on_text=None):
                self.calls += 1
                if self.calls == 1:
                    raise asyncio.CancelledError
                return "The second request completed."

        prompt = FakePrompt()
        ui = FakeUI()
        conversation = FakeConversation()
        with patch("cli.prompt.InteractivePrompt", return_value=prompt):
            with patch("cli.terminal_ui.TerminalUI", return_value=ui):
                with patch("cli.app._new_conversation", return_value=conversation):
                    result = asyncio.run(_interactive(object(), None))

        self.assertEqual(result, 0)
        self.assertEqual(conversation.calls, 2)
        self.assertTrue(any("Pedido interrompido" in message for message in ui.messages))
        self.assertEqual(ui.answers, ["The second request completed."])

    def test_quick_question_flags_cannot_be_combined_with_subcommands(self):
        with self.assertRaises(SystemExit):
            main(["-q", "hello", "chat"])

    def test_terminal_ui_formats_banner_responses_and_tool_logs_with_plain_fallback(self):
        from cli.client import TerminalClient
        from cli.terminal_ui import TerminalUI

        output = []
        errors = []
        ui = TerminalUI(output=output.append, error_output=errors.append)
        terminal = TerminalClient(output=ui.system, error=ui.error)

        ui.banner()
        ui.assistant("**Ready**")
        terminal.write_log("SYS: Opening Calculator.")
        terminal.write_log("ERR: Tool failed.")

        self.assertIn(".---.", output[0])
        self.assertIn("ARGUS CLI v", output[1])
        self.assertIn("ARGUS> **Ready**", output[2])
        self.assertEqual(output[3], "[ARGUS] Opening Calculator.")
        self.assertEqual(errors, ["[ARGUS] Tool failed."])

    def test_eye_banner_fits_the_terminal_budget_and_uses_ascii(self):
        from cli.banner import EYE_BANNER

        lines = EYE_BANNER.splitlines()
        self.assertLessEqual(len(lines), 12)
        self.assertLessEqual(max(map(len, lines)), 60)
        self.assertTrue(EYE_BANNER.isascii())

    def test_terminal_ui_renders_markdown_with_rich_when_available(self):
        from rich.console import Console

        from cli.terminal_ui import TerminalUI

        output = StringIO()
        errors = StringIO()
        ui = TerminalUI(
            console=Console(file=output, force_terminal=False, width=100),
            error_console=Console(file=errors, force_terminal=False, width=100),
        )

        ui.banner()
        ui.assistant("**Ready**")
        ui.system("Opening Calculator.")
        ui.error("[ARGUS] Tool failed.")

        rendered = output.getvalue()
        self.assertIn("ARGUS", rendered)
        self.assertIn("Ready", rendered)
        self.assertNotIn("**Ready**", rendered)
        self.assertIn("Opening Calculator.", rendered)
        self.assertIn("Tool failed.", errors.getvalue())

    def test_interactive_prompt_reuses_file_history_with_private_permissions(self):
        from prompt_toolkit.history import FileHistory

        from cli.prompt import InteractivePrompt

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "prompt-history"

            class RecordingSession:
                def __init__(self):
                    self.history = FileHistory(str(path))
                    self.calls = 0

                def prompt(self, _message):
                    self.calls += 1
                    self.history.append_string(f"turn {self.calls}")
                    return f"turn {self.calls}"

            session = RecordingSession()
            prompt = InteractivePrompt(
                history_path=path,
                session_factory=lambda _path: session,
                interactive=True,
            )

            self.assertEqual(prompt.prompt("You> "), "turn 1")
            self.assertEqual(prompt.prompt("You> "), "turn 2")
            self.assertEqual(session.history.get_strings(), ["turn 1", "turn 2"])
            self.assertTrue(path.exists())
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_interactive_prompt_completes_slash_commands(self):
        from prompt_toolkit.completion import CompleteEvent
        from prompt_toolkit.document import Document

        from cli.prompt import InteractivePrompt, create_slash_completer

        with tempfile.TemporaryDirectory() as temp_dir:
            completer = create_slash_completer()
            completions = list(
                completer.get_completions(Document("/he"), CompleteEvent())
            )
        self.assertEqual([item.text for item in completions], ["/help"])

    def test_voice_command_dispatches_without_opening_text_session_storage(self):
        with patch("cli.app._run_voice", return_value=0) as run_voice:
            with patch("cli.app.SessionStore") as store:
                self.assertEqual(main(["voice"]), 0)
        run_voice.assert_called_once_with()
        store.assert_not_called()

    def test_explicit_voice_command_falls_back_to_text_when_audio_is_unavailable(self):
        from cli.voice import VOICE_UNAVAILABLE

        store = object()
        with patch("cli.voice.run_voice", return_value=VOICE_UNAVAILABLE):
            with patch("cli.app.SessionStore", return_value=store):
                with patch("cli.app._interactive", new_callable=AsyncMock, return_value=0) as chat:
                    with patch("builtins.print") as output:
                        self.assertEqual(main(["voice"]), 0)

        chat.assert_awaited_once_with(store, None)
        output.assert_any_call(
            "A voz não está disponível; iniciando uma sessão de texto."
        )

    def test_no_subcommand_uses_saved_voice_preference_but_chat_forces_text(self):
        with patch("cli.app._default_voice_enabled", return_value=True) as preference:
            with patch("cli.app._run_voice", return_value=0) as run_voice:
                with patch("cli.app.SessionStore") as store:
                    self.assertEqual(main([]), 0)
        preference.assert_called_once_with()
        run_voice.assert_called_once_with()
        store.assert_not_called()

        def close_interactive(coroutine):
            coroutine.close()
            return 0

        with patch("cli.app._default_voice_enabled") as preference:
            with patch("cli.app.SessionStore", return_value=object()):
                with patch("cli.app.asyncio.run", side_effect=close_interactive):
                    self.assertEqual(main(["chat"]), 0)
        preference.assert_not_called()

    def test_saved_voice_default_falls_back_to_text_when_audio_is_unavailable(self):
        from cli.voice import VOICE_UNAVAILABLE

        store = object()
        with patch("cli.app._default_voice_enabled", return_value=True):
            with patch("cli.voice.run_voice", return_value=VOICE_UNAVAILABLE):
                with patch("cli.app.SessionStore", return_value=store):
                    with patch("cli.app._interactive", new_callable=AsyncMock, return_value=0) as chat:
                        self.assertEqual(main([]), 0)

        chat.assert_awaited_once_with(store, None)

    def test_voice_terminal_client_prints_complete_transcripts_and_system_logs(self):
        from cli.voice import VoiceTerminalClient

        output = []
        client = VoiceTerminalClient(output=output.append)
        client.write_log("You: Abra o Spotify")
        client.show_subtitle("A música")
        client.show_subtitle(" está tocando.")
        client.write_log("Argus: A música está tocando.")
        client.write_log("SYS: Gemini Live connected.")
        self.assertEqual(
            output,
            ["Você> Abra o Spotify", "ARGUS> A música está tocando.", "[ARGUS] Gemini Live connected."],
        )

    def test_voice_mode_explains_optional_audio_dependency_without_importing_desktop_app(self):
        from cli.voice import VOICE_UNAVAILABLE, run_voice

        output = []
        with patch("cli.voice.importlib.util.find_spec", return_value=None):
            result = run_voice(output=output.append, audio_available=lambda: False)
        self.assertEqual(result, VOICE_UNAVAILABLE)
        self.assertTrue(any("optional [voice] extra" in line for line in output))

    def test_voice_mode_falls_back_when_no_microphone_or_speaker_is_available(self):
        from cli.voice import VOICE_UNAVAILABLE, run_voice

        output = []
        result = run_voice(
            output=output.append,
            audio_available=lambda: True,
            audio_devices_loader=lambda: [
                {"max_input_channels": 0, "max_output_channels": 0}
            ],
        )

        self.assertEqual(result, VOICE_UNAVAILABLE)
        self.assertTrue(any("microphone and speaker" in line for line in output))

    def test_voice_mode_uses_saved_settings_and_closes_cleanly_on_interrupt(self):
        from cli.voice import VoiceTerminalClient, run_voice

        class FakeAssistant:
            def __init__(self, client, voice_name, *, api_key):
                self.client = client
                self.voice_name = voice_name
                self.api_key = api_key
                self.stopped = False

            async def run(self):
                await asyncio.sleep(0)

            def request_shutdown(self):
                self.stopped = True

        settings = SimpleNamespace(voice=SimpleNamespace(name="kore"))
        created = []

        def factory(*args, **kwargs):
            assistant = FakeAssistant(*args, **kwargs)
            created.append(assistant)
            return assistant

        def interrupted(coroutine):
            coroutine.close()
            raise KeyboardInterrupt

        output = []
        result = run_voice(
            output=output.append,
            live_factory=factory,
            settings_loader=lambda: settings,
            api_key_loader=lambda: "fake-key",
            async_runner=interrupted,
        )
        self.assertEqual(result, 130)
        self.assertEqual(created[0].voice_name, "kore")
        self.assertEqual(created[0].api_key, "fake-key")
        self.assertIsInstance(created[0].client, VoiceTerminalClient)
        self.assertTrue(created[0].stopped)
        self.assertIn("ARGUS voice session ended.", output)

    def test_voice_mode_handles_engine_initialization_errors_without_traceback(self):
        from cli.voice import run_voice

        output = []
        result = run_voice(
            output=output.append,
            live_factory=Mock(side_effect=RuntimeError("private provider detail")),
            settings_loader=lambda: SimpleNamespace(voice=SimpleNamespace(name="kore")),
            api_key_loader=lambda: "fake-key",
        )
        self.assertEqual(result, 2)
        self.assertEqual(output, ["Could not initialize voice mode (RuntimeError)."])

    def test_debug_screens_flag_enables_private_screenshot_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "ARGUS_SESSION_DB": str(Path(temp_dir) / "sessions.sqlite3"),
                    "ARGUS_DEBUG_SCREENSHOTS": "false",
                },
            ):
                self.assertEqual(main(["--debug-screens", "sessions"]), 0)
                self.assertEqual(os.environ["ARGUS_DEBUG_SCREENSHOTS"], "true")

    def test_sessions_command_does_not_load_model_or_audio_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            from unittest.mock import patch

            with patch.dict(sys.modules, {"main": None, "sounddevice": None}):
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

    def test_text_turn_streams_chunks_and_persists_the_complete_response(self):
        class StreamingModels:
            def __init__(self):
                self.responses = [
                    [
                        SimpleNamespace(
                            text="A calm ",
                            candidates=[
                                SimpleNamespace(
                                    content=types.Content(
                                        role="model",
                                        parts=[types.Part(text="A calm ")],
                                    )
                                )
                            ],
                        ),
                        SimpleNamespace(
                            text="answer.",
                            candidates=[
                                SimpleNamespace(
                                    content=types.Content(
                                        role="model",
                                        parts=[types.Part(text="answer.")],
                                    )
                                )
                            ],
                        ),
                    ]
                ]

            async def generate_content_stream(self, **_kwargs):
                chunks = self.responses.pop(0)

                async def stream():
                    for chunk in chunks:
                        yield chunk

                return stream()

        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=Mock()),
            aio=SimpleNamespace(models=StreamingModels()),
        )
        conversation = TextConversation(
            self.session_id,
            self.store,
            client=client,
            registry=FakeRegistry(),
            system_instruction="test system instruction",
        )
        streamed = []

        answer = asyncio.run(conversation.ask("Give me a calm answer.", on_text=streamed.append))

        self.assertEqual(answer, "A calm answer.")
        self.assertEqual(streamed, ["A calm ", "answer."])
        saved = self.store.load_history(self.session_id)
        self.assertEqual(saved[-1]["parts"][0]["text"], "A calm answer.")

    def test_streamed_function_call_is_executed_once_before_streaming_the_answer(self):
        class StreamingModels:
            def __init__(self):
                self.responses = [
                    [
                        SimpleNamespace(
                            text=None,
                            candidates=[
                                SimpleNamespace(
                                    content=types.Content(
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
                                )
                            ],
                        )
                    ],
                    [
                        SimpleNamespace(
                            text="Calculator is open.",
                            candidates=[
                                SimpleNamespace(
                                    content=types.Content(
                                        role="model",
                                        parts=[types.Part(text="Calculator is open.")],
                                    )
                                )
                            ],
                        )
                    ],
                ]

            async def generate_content_stream(self, **_kwargs):
                chunks = self.responses.pop(0)

                async def stream():
                    for chunk in chunks:
                        yield chunk

                return stream()

        registry = FakeRegistry()
        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=Mock()),
            aio=SimpleNamespace(models=StreamingModels()),
        )
        conversation = TextConversation(
            self.session_id,
            self.store,
            client=client,
            registry=registry,
            system_instruction="test system instruction",
        )
        streamed = []

        answer = asyncio.run(conversation.ask("Open Calculator", on_text=streamed.append))

        self.assertEqual(answer, "Calculator is open.")
        self.assertEqual(streamed, ["Calculator is open."])
        registry.execute.assert_awaited_once_with(
            name="open_app",
            ctx=conversation._tool_context,
            args={"app_name": "Calculator"},
        )

    def test_cancelled_turn_rolls_back_partial_model_history(self):
        async def run_cancelled_turn():
            started = asyncio.Event()
            never = asyncio.Event()

            class BlockingModels:
                async def generate_content_stream(self, **_kwargs):
                    started.set()

                    async def stream():
                        await never.wait()
                        yield SimpleNamespace(text="unreachable", candidates=[])

                    return stream()

            client = SimpleNamespace(
                models=SimpleNamespace(generate_content=Mock()),
                aio=SimpleNamespace(models=BlockingModels()),
            )
            conversation = TextConversation(
                self.session_id,
                self.store,
                client=client,
                registry=FakeRegistry(),
                system_instruction="test system instruction",
            )
            request = asyncio.create_task(
                conversation.ask("Cancel this request.", on_text=lambda _chunk: None)
            )
            await started.wait()
            request.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await request
            self.assertEqual(conversation.history, [])
            self.assertEqual(self.store.load_history(self.session_id), [])

        asyncio.run(run_cancelled_turn())


if __name__ == "__main__":
    unittest.main()
