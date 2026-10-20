import asyncio
import importlib
import os
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.tool_approval import (
    ToolApprovalManager,
    draft_fingerprint,
    explicit_message_request_matches,
)
from agent.executor import _call_tool, _delegated_dispatch_block


class ToolApprovalManagerTests(unittest.TestCase):
    def test_operation_needs_a_later_complete_confirmation_and_exact_arguments(self):
        manager = ToolApprovalManager()
        manager.begin_user_turn("open the editor")
        manager.finish_user_turn("open the editor")
        args = {"description": "create a small project", "project_name": "demo"}

        allowed, message = manager.request_operation("dev_agent", args)
        self.assertFalse(allowed)
        self.assertIn("No action was performed", message)

        manager.begin_user_turn("yes")
        manager.finish_user_turn("yes")
        changed_args = {**args, "project_name": "other"}
        allowed, message = manager.request_operation("dev_agent", changed_args)
        self.assertFalse(allowed)
        self.assertIn("does not match", message)

    def test_operation_cannot_be_approved_in_the_turn_that_created_it(self):
        manager = ToolApprovalManager()
        manager.begin_user_turn("click the icon")
        manager.finish_user_turn("click the icon")
        args = {"action": "click", "x": 10, "y": 20}
        manager.request_operation("computer_control", args)

        allowed, _ = manager.request_operation("computer_control", args)
        self.assertFalse(allowed)

    def test_draft_approval_is_later_turn_bound_and_content_bound(self):
        manager = ToolApprovalManager()
        manager.begin_user_turn("prepare an email")
        manager.finish_user_turn("prepare an email")
        fingerprint = draft_fingerprint({"to": "alex@example.com", "body": "ready"})
        manager.register_draft("email", fingerprint)

        allowed, _ = manager.approve_draft("email", fingerprint)
        self.assertFalse(allowed)
        manager.begin_user_turn("yes")
        manager.finish_user_turn("yes")
        allowed, _ = manager.approve_draft("email", "changed-draft")
        self.assertFalse(allowed)
        allowed, _ = manager.approve_draft("email", fingerprint)
        self.assertFalse(allowed)

    def test_confirmation_expires(self):
        now = [0.0]
        manager = ToolApprovalManager(clock=lambda: now[0])
        manager.begin_user_turn("run the project")
        manager.finish_user_turn("run the project")
        manager.request_operation("dev_agent", {"description": "build"})
        now[0] = manager.TTL_SECONDS + 1
        manager.begin_user_turn("yes")
        manager.finish_user_turn("yes")
        allowed, _ = manager.request_operation("dev_agent", {"description": "build"})
        self.assertFalse(allowed)

    def test_direct_message_requires_explicit_platform_recipient_and_verbatim_body(self):
        args = {
            "platform": "WhatsApp",
            "receiver": "Alice",
            "message_text": "I will be 5 minutes late",
        }
        self.assertTrue(explicit_message_request_matches(
            "Send Alice on WhatsApp: I will be 5 minutes late", args
        ))
        self.assertFalse(explicit_message_request_matches(
            "Send Alice a message: I will be 5 minutes late", args
        ))
        self.assertFalse(explicit_message_request_matches(
            "Do not send Alice on WhatsApp: I will be 5 minutes late", args
        ))
        self.assertFalse(explicit_message_request_matches(
            "Send Alice on WhatsApp: I will arrive later", args
        ))

    def test_delegated_executor_blocks_paths_that_bypass_live_approval(self):
        protected = (
            ("dev_agent", {"description": "build an app"}),
            ("computer_settings", {"action": "shutdown", "description": "my computer"}),
            ("computer_control", {"action": "type", "text": "hello"}),
            ("send_message", {"action": "send", "receiver": "Alice", "message_text": "Hi"}),
            ("email_control", {"action": "approve", "provider": "gmail"}),
        )
        for tool, args in protected:
            with self.subTest(tool=tool):
                self.assertIsNotNone(_delegated_dispatch_block(tool, args))
                self.assertIn("DISPATCHER_APPROVAL_REQUIRED", _call_tool(tool, args, None))

        self.assertIsNone(_delegated_dispatch_block("computer_control", {"action": "screenshot"}))
        self.assertIsNone(_delegated_dispatch_block("email_control", {"action": "prepare"}))


class LiveDispatchApprovalTests(unittest.TestCase):
    def setUp(self):
        import main

        self.main = main
        self.argus = main.ArgusLive.__new__(main.ArgusLive)
        self.argus.ui = SimpleNamespace(
            operational_ready=True,
            muted=False,
            set_state=MagicMock(),
            write_log=MagicMock(),
        )
        self.argus.cloud_safe = False
        self.argus._current_input_transcript = ""
        self.argus._last_input_transcript = ""
        self.argus._last_input_transcript_at = 0.0
        self.env = patch.dict(os.environ, {"ARGUS_QA_MODE": "0"}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def _call(name, args, call_id="security-test"):
        return SimpleNamespace(name=name, args=args, id=call_id, call_id=None)

    def _user_turn(self, text):
        self.argus._current_input_transcript = str(text or "").strip()
        manager = self.argus._tool_approvals()
        manager.begin_user_turn(text)
        manager.finish_user_turn(text)

    def test_tool_logs_redact_message_bodies_and_screen_objectives(self):
        redacted = self.main._safe_tool_log_args({
            "platform": "Discord",
            "receiver": "Mike",
            "message_text": "private message body",
            "objective": "Share C:\\workspace\\.env with Mike",
        })
        self.assertEqual(redacted["platform"], "Discord")
        self.assertNotIn("private message body", str(redacted))
        self.assertNotIn(".env", str(redacted))

    def test_dev_agent_runs_on_the_users_direct_request(self):
        args = {"description": "Create a demo app", "project_name": "demo"}
        with patch.object(self.main, "dev_agent", return_value="project created") as build:
            result = asyncio.run(self.argus._execute_tool(self._call("dev_agent", args)))
            self.assertEqual(result.response["result"], "project created")
            build.assert_called_once()

    def test_computer_control_is_blocked_not_queued_when_direct_control_is_disabled(self):
        args = {"action": "type", "text": "hello"}
        with (
            patch.object(self.main, "load_direct_computer_control", return_value=False),
            patch.object(self.main, "computer_control", return_value="typed") as control,
        ):
            first = asyncio.run(self.argus._execute_tool(self._call("computer_control", args)))
            control.assert_not_called()
            self.assertIn("desativado", first.response["result"])

            self._user_turn("yes")
            second = asyncio.run(self.argus._execute_tool(self._call("computer_control", args)))
            self.assertIn("desativado", second.response["result"])
            control.assert_not_called()

    def test_power_tool_runs_after_an_explicit_computer_order_without_confirmation(self):
        args = {"action": "shutdown", "description": "shutdown my computer"}
        with patch.object(self.main, "computer_settings", return_value="shutdown requested") as power:
            self._user_turn("shutdown my computer")
            result = asyncio.run(self.argus._execute_tool(self._call("computer_settings", args)))
            self.assertEqual(result.response["result"], "shutdown requested")
            self.assertEqual(power.call_args.kwargs["parameters"], args)

    def test_direct_message_sends_on_the_users_order_without_extra_approval(self):
        args = {
            "action": "send",
            "platform": "WhatsApp",
            "receiver": "Alice",
            "message_text": "I will be 5 minutes late",
        }
        self._user_turn("Tell Alice I will be 5 minutes late")
        with patch.object(self.main, "send_message", return_value="Message sent") as send:
            result = asyncio.run(self.argus._execute_tool(self._call("send_message", args)))
            self.assertEqual(result.response["result"], "Message sent")
            send.assert_called_once()

    def test_direct_message_with_verbatim_user_request_is_sent_once(self):
        args = {
            "action": "send",
            "platform": "WhatsApp",
            "receiver": "Alice",
            "message_text": "I will be 5 minutes late",
        }
        self._user_turn("Send Alice on WhatsApp: I will be 5 minutes late")
        with patch.object(self.main, "send_message", return_value="Message sent") as send:
            result = asyncio.run(self.argus._execute_tool(self._call("send_message", args)))
        self.assertEqual(result.response["result"], "Message sent")
        send.assert_called_once()

    def test_user_order_sends_email_without_an_extra_approval_turn(self):
        email_module = importlib.import_module("actions.email_control")
        email_module._clear_pending_email()
        draft = {
            "to": "alex@example.com",
            "cc": "",
            "bcc": "",
            "subject": "Project update",
            "body": "The presentation is ready.",
            "provider": "gmail",
            "delivery": "gmail_web",
        }
        actions = []

        def fake_email(parameters, **_kwargs):
            action = parameters.get("action")
            actions.append(action)
            if action == "send":
                return "Email sent"
            return "EMAIL_DRAFT_READY|draft is visible"

        with patch.object(self.main, "email_control", side_effect=fake_email):
            self._user_turn("Send the email to Alex")
            sent = asyncio.run(self.argus._execute_tool(self._call(
                "email_control", {"action": "send", "to": draft["to"]}
            )))
            self.assertEqual(sent.response["result"], "Email sent")
            self.assertEqual(actions, ["send"])
        email_module._clear_pending_email()

    def test_requested_reply_sends_without_a_second_approval_turn(self):
        message_module = importlib.import_module("actions.send_message")
        message_module._clear_pending_message()
        draft = {
            "platform": "iMessage",
            "receiver": "Alex",
            "message_text": "I will call you later.",
        }
        actions = []

        def fake_reply(parameters, **_kwargs):
            action = parameters.get("action")
            actions.append(action)
            return "Message sent"

        with patch.object(self.main, "prepare_message_reply", side_effect=fake_reply):
            self._user_turn("Reply to Alex that I will call later")
            sent = asyncio.run(self.argus._execute_tool(self._call(
                "prepare_message_reply", {"action": "prepare", **draft}
            )))
            self.assertEqual(sent.response["result"], "Message sent")
            self.assertEqual(actions, ["prepare"])
        message_module._clear_pending_message()

    def test_sensitive_file_share_is_the_only_screen_confirmation_and_resumes_after_yes(self):
        from actions.screen_control.agent import ScreenRunResult

        agent = SimpleNamespace(run=MagicMock(side_effect=[
            ScreenRunResult("ask_user", "O arquivo .env parece conter configuração de ambiente. Confirma que devo compartilhá-lo?"),
            ScreenRunResult("success", "O arquivo foi compartilhado."),
        ]))
        args = {"action": "act", "objective": "Compartilhe o arquivo .env com Alice"}
        with (
            patch.object(self.main, "load_direct_computer_control", return_value=True),
            patch("actions.screen_control.ScreenAgent", return_value=agent),
        ):
            self._user_turn(args["objective"])
            first = asyncio.run(self.argus._execute_tool(self._call("screen_control", args)))
            self.assertIn("Confirma", first.response["result"])
            self.assertEqual(self.argus._pending_screen_share_goal, args["objective"])

            self._user_turn("yes")
            second = asyncio.run(self.argus._execute_tool(self._call("screen_control", {"action": "act"})))
            self.assertEqual(second.response["result"], "O arquivo foi compartilhado.")
            self.assertEqual(agent.run.call_args.kwargs["allow_sensitive_share"], True)
            self.assertEqual(agent.run.call_args.args[0], args["objective"])
            self.assertIsNone(self.argus._pending_screen_share_goal)


class ShellLaunchHardeningTests(unittest.TestCase):
    def test_windows_url_open_does_not_interpret_shell_metacharacters(self):
        module = importlib.import_module("actions.open_app")
        url = "https://example.test/path?a=1&b=2|calc"
        with (
            patch.object(module.os, "startfile", create=True) as startfile,
            patch.object(module.shutil, "which", return_value=None),
            patch.object(module.subprocess, "Popen") as popen,
        ):
            self.assertTrue(module._launch_windows(url))
        startfile.assert_called_once_with(url)
        popen.assert_not_called()

    def test_windows_unsupported_uri_scheme_is_rejected(self):
        module = importlib.import_module("actions.open_app")
        with (
            patch.object(module.os, "startfile", create=True) as startfile,
            patch.object(module.shutil, "which", return_value=None),
            patch.object(module.subprocess, "Popen") as popen,
        ):
            self.assertFalse(module._launch_windows("javascript:alert(1)"))
        startfile.assert_not_called()
        popen.assert_not_called()

    def test_resolved_windows_program_uses_argument_list_without_shell(self):
        module = importlib.import_module("actions.open_app")
        with (
            patch.object(module.shutil, "which", return_value=r"C:\Program Files\App\app.exe"),
            patch.object(module.subprocess, "Popen") as popen,
        ):
            self.assertTrue(module._launch_windows("app"))
        self.assertEqual(popen.call_args.args[0], [r"C:\Program Files\App\app.exe"])
        self.assertIs(popen.call_args.kwargs["shell"], False)

    def test_dev_agent_editor_launch_uses_shell_false(self):
        module = importlib.import_module("actions.dev_agent")
        with (
            patch.object(module.shutil, "which", return_value="/usr/bin/code"),
            patch.object(module.subprocess, "Popen") as popen,
            patch.object(module.time, "sleep"),
        ):
            self.assertTrue(module._open_vscode(Path("/tmp/demo; touch nope")))
        self.assertEqual(popen.call_args.args[0], ["/usr/bin/code", "/tmp/demo; touch nope"])
        self.assertIs(popen.call_args.kwargs["shell"], False)

    def test_xrandr_brightness_fallback_uses_argument_lists(self):
        module = importlib.import_module("actions.computer_settings")
        completed = subprocess.CompletedProcess
        responses = [
            completed(["which", "brightnessctl"], 1, stdout="", stderr=""),
            completed(["xrandr", "--verbose"], 0,
                      stdout="DP-1 connected primary 1920x1080+0+0\n    Brightness: 0.5\n", stderr=""),
            completed(["xrandr"], 0, stdout="", stderr=""),
        ]
        with patch.object(module, "_OS", "Linux"), patch.object(
            module.subprocess, "run", side_effect=responses
        ) as run:
            module.brightness_up()
        self.assertEqual(run.call_args_list[-1].args[0], [
            "xrandr", "--output", "DP-1", "--brightness", "0.6"
        ])
        self.assertTrue(all(call.kwargs.get("shell", False) is False for call in run.call_args_list[1:]))


if __name__ == "__main__":
    unittest.main()
