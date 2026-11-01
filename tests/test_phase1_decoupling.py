import asyncio
import unittest
from types import SimpleNamespace

from core.argus_client import ArgusClient, ArgusDesktopClient
import main
from tools import impl as tool_impl
from tools.registry import ToolContext


class StubClient:
    def __init__(self):
        self.on_text_command = None
        self.muted = False
        self.current_file = None
        self._voice_combo = None
        self.events = []

    def write_log(self, text):
        self.events.append(("log", text))

    def set_state(self, state):
        self.events.append(("state", state))

    def show_subtitle(self, text):
        self.events.append(("subtitle", text))

    def clear_subtitle(self):
        self.events.append(("subtitle", None))

    def set_theme(self, theme_key):
        self.events.append(("theme", theme_key))

    def set_graphics_quality(self, quality):
        self.events.append(("graphics", quality))

    def sync_voice_display(self, voice_name):
        self.events.append(("voice", voice_name))

    def handle_ui_command(self, action):
        self.events.append(("ui", action))


class HeadlessClient:
    """Conversation events only; intentionally has no desktop state or controls."""

    def __init__(self):
        self.on_text_command = None
        self.events = []

    def write_log(self, text):
        self.events.append(("log", text))

    def set_state(self, state):
        self.events.append(("state", state))

    def show_subtitle(self, text):
        self.events.append(("subtitle", text))

    def clear_subtitle(self):
        self.events.append(("subtitle", None))


class PhaseOneDecouplingTests(unittest.TestCase):
    def test_desktop_adapter_exposes_the_engine_contract(self):
        from ui import ArgusUI

        core_members = {
            "on_text_command",
            "write_log",
            "set_state",
            "show_subtitle",
            "clear_subtitle",
        }
        desktop_capabilities = {
            "muted",
            "current_file",
            "_voice_combo",
            "set_theme",
            "set_graphics_quality",
            "sync_voice_display",
            "handle_ui_command",
        }

        self.assertFalse(core_members - set(dir(ArgusUI)))
        self.assertFalse(desktop_capabilities - set(dir(ArgusUI)))

    def test_client_protocol_and_text_callback_are_wired(self):
        client = StubClient()
        self.assertIsInstance(client, ArgusClient)
        self.assertIsInstance(client, ArgusDesktopClient)

        argus = main.ArgusLive(client)

        self.assertIs(argus.client, client)
        self.assertIs(argus.ui, client)
        self.assertEqual(client.on_text_command, argus._on_text_command)

    def test_headless_client_needs_only_conversation_events(self):
        client = HeadlessClient()
        self.assertIsInstance(client, ArgusClient)
        self.assertNotIsInstance(client, ArgusDesktopClient)

        argus = main.ArgusLive(client)

        self.assertIs(argus.client, client)
        self.assertEqual(client.on_text_command, argus._on_text_command)
        self.assertFalse(argus._is_muted())
        self.assertIsNone(argus._current_file())

    def test_desktop_only_tool_reports_missing_capability_to_headless_client(self):
        client = HeadlessClient()
        argus = main.ArgusLive(client)
        call = SimpleNamespace(id="graphics-call", name="graphics_quality", args={"quality": "high"})

        response = asyncio.run(argus._execute_tool(call))

        self.assertEqual(
            response.response["result"],
            "Graphics quality controls are unavailable for this client.",
        )

    def test_tool_context_uses_client_and_keeps_legacy_ui_alias(self):
        client = HeadlessClient()
        speak = lambda _text: True
        context = ToolContext(client=client, speak=speak, speak_vision_result=speak)
        legacy_context = ToolContext(ui=client, speak=speak, speak_vision_result=speak)

        self.assertIs(context.client, client)
        self.assertIs(context.ui, client)
        self.assertIs(legacy_context.client, client)

    def test_registry_tool_adapter_handles_missing_desktop_capabilities(self):
        client = HeadlessClient()
        speak = lambda _text: True
        context = ToolContext(client=client, speak=speak, speak_vision_result=speak)

        graphics = asyncio.run(
            tool_impl.execute(context, "graphics_quality", {"quality": "high"})
        )
        theme = asyncio.run(
            tool_impl.execute(
                context,
                "argus_ui_control",
                {"action": "change_theme", "theme": "platinum"},
            )
        )

        self.assertIn("unavailable for this client", graphics["result"])
        self.assertIn("unavailable for this client", theme["result"])

    def test_desktop_mode_keeps_the_complete_tool_inventory(self):
        client = StubClient()
        argus = main.ArgusLive(client)

        self.assertFalse(argus.cloud_safe)
        self.assertEqual(argus.tool_declarations, main.TOOL_DECLARATIONS)

    def test_cloud_safe_mode_loads_only_the_hosted_allowlist(self):
        client = StubClient()
        argus = main.ArgusLive(client, cloud_safe=True)
        names = {item["name"] for item in argus.tool_declarations}

        self.assertEqual(names, main.CLOUD_SAFE_ACTIONS)
        self.assertTrue(names.isdisjoint(main.LOCAL_MACHINE_ONLY_ACTIONS))

    def test_cloud_safe_mode_rejects_unadvertised_local_tool_calls(self):
        client = StubClient()
        argus = main.ArgusLive(client, cloud_safe=True)
        call = SimpleNamespace(id="local-call", name="open_app", args={})

        response = asyncio.run(argus._execute_tool(call))

        self.assertIn("unavailable in cloud-safe mode", response.response["result"])
        self.assertEqual(client.events, [])


if __name__ == "__main__":
    unittest.main()
