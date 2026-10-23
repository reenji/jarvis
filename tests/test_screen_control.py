from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from actions.screen_control.actions import to_absolute, ActionResult
from actions.screen_control.agent import ScreenAgent
from actions.screen_control.capture import Capture
from actions.screen_control.config import ScreenConfig
from actions.screen_control.schemas import ActionType, ScreenAction
from actions.screen_control.safety import sensitive_file_reason
from actions.screen_control.window import WindowInfo
from actions.screen_control.agent import _share_intent, _sensitive_visible_file
from actions.screen_control.safety import is_blocked_process, is_blocked_terminal_target


def _capture(*, left=0, top=0, source_width=1000, source_height=600, scale=1.0):
    width = round(source_width * scale)
    height = round(source_height * scale)
    window = WindowInfo("Discord", "discord.exe", left, top, source_width, source_height, 42)
    return Capture(b"same screenshot", width, height, source_width, source_height, left, top, scale, 0.0, window)


@pytest.mark.parametrize(
    ("source_width", "source_height", "scale", "origin", "point", "expected"),
    [
        (1000, 600, 1.0, (0, 0), (500, 500), (500, 300)),
        (1250, 750, 0.8, (20, 40), (500, 500), (644, 414)),
        (1500, 900, 0.6666667, (-1920, 100), (500, 500), (-1170, 550)),
    ],
)
def test_normalized_coordinates_use_source_pixels_and_window_origin(
    source_width, source_height, scale, origin, point, expected
):
    capture = _capture(
        left=origin[0], top=origin[1], source_width=source_width,
        source_height=source_height, scale=scale,
    )
    assert to_absolute(*point, capture) == expected


def test_screen_action_schema_rejects_bad_coordinates_and_unknown_actions():
    with pytest.raises(ValueError, match="entre 0 e 1000"):
        ScreenAction.from_json({"action": "click", "x": 1001, "y": 20})
    with pytest.raises(ValueError, match="desconhecida"):
        ScreenAction.from_json({"action": "launch"})


def test_screen_action_schema_parses_one_valid_action():
    action = ScreenAction.from_json(
        '{"action":"click","x":500,"y":250,"target_description":"Mike"}'
    )
    assert action.action is ActionType.CLICK
    assert action.target_description == "Mike"


def test_sensitive_file_detection_covers_env_docker_and_secret_contents():
    assert "ambiente" in sensitive_file_reason("C:/project/.env")
    assert "configuração operacional" in sensitive_file_reason("docker-compose.yml")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.txt"
        path.write_text("ARGUS_API_KEY=not-for-sharing", encoding="utf-8")
        result = sensitive_file_reason(str(path))
        assert result and "credencial" in result
        assert "not-for-sharing" not in result


def test_file_confirmation_policy_only_triggers_for_file_sharing():
    assert _share_intent("Compartilhe o arquivo docker-compose.yml com a equipe")
    assert not _share_intent("Compartilhe minha tela do Discord com a equipe")
    assert _sensitive_visible_file("Abra C:\\workspace\\.env no editor", []) is None
    assert _sensitive_visible_file("Compartilhe C:\\workspace\\.env", []) is not None


@pytest.mark.parametrize("process", ["WindowsTerminal.exe", "powershell.exe", "gnome-terminal-server", "iTerm2"])
def test_terminal_processes_are_blocked_as_screen_targets(process):
    assert is_blocked_process(process)


@pytest.mark.parametrize("target", ["Windows Terminal", "PowerShell", "cmd.exe", "iTerm2", "Terminal"])
def test_terminal_names_are_blocked_as_requested_window_targets(target):
    assert is_blocked_terminal_target(target)


def test_focus_delay_is_configurable_and_bounded_by_environment():
    with patch.dict("os.environ", {"ARGUS_SCREEN_FOCUS_DELAY": "2.5"}):
        assert ScreenConfig.from_env().focus_delay == 2.5
    with patch.dict("os.environ", {"ARGUS_SCREEN_FOCUS_DELAY": "99"}):
        assert ScreenConfig.from_env().focus_delay == 10
    with patch.dict("os.environ", {"ARGUS_SCREEN_FOCUS_DELAY": "invalid"}):
        assert ScreenConfig.from_env().focus_delay == ScreenConfig.focus_delay


def test_debug_screenshots_are_opt_in_and_saved_in_user_debug_directory():
    from PIL import Image

    image = Image.new("RGB", (2, 2), color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    capture = _capture()
    capture = Capture(
        output.getvalue(), capture.image_width, capture.image_height,
        capture.source_width, capture.source_height, capture.origin_x,
        capture.origin_y, capture.scale, capture.timestamp, capture.window,
    )
    agent = ScreenAgent(config=ScreenConfig(debug_screenshots=True), abort_controller=_NoopAbort())
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir) / "argus"
        with patch("actions.screen_control.agent.default_argus_data_dir", return_value=root):
            agent._write_step_debug("run-123", 1, capture, ScreenAction(ActionType.CLICK, x=500, y=500))
        assert (root / "debug" / "screens" / "run-123" / "step-01.png").is_file()


def test_active_terminal_window_fails_closed_before_capture():
    from types import SimpleNamespace
    from actions.screen_control.window import get_active_window

    win32gui = SimpleNamespace(
        GetForegroundWindow=lambda: 100,
        GetWindowText=lambda _handle: "PowerShell - C:\\workspace",
        GetWindowRect=lambda _handle: (0, 0, 1280, 720),
    )
    win32process = SimpleNamespace(GetWindowThreadProcessId=lambda _handle: (7, 123))
    psutil = SimpleNamespace(Process=lambda _pid: SimpleNamespace(name=lambda: "WindowsTerminal.exe"))
    with patch.dict("sys.modules", {"win32gui": win32gui, "win32process": win32process, "psutil": psutil}):
        with pytest.raises(RuntimeError, match="terminal é protegida"):
            get_active_window()


class _NoopAbort:
    aborted = False

    def start(self):
        pass

    def stop(self):
        pass


def test_screen_agent_verifies_success_after_two_observations():
    capture = _capture()
    agent = ScreenAgent(
        config=ScreenConfig(max_steps=4, max_seconds=10, settle_delay=0.1),
        abort_controller=_NoopAbort(),
    )
    click = ScreenAction(ActionType.CLICK, target_description="Mike", x=300, y=400)
    done = ScreenAction(ActionType.DONE, summary="A conversa com Mike está aberta.")
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action", side_effect=[click, done]),
        patch("actions.screen_control.agent.execute", return_value=ActionResult(True, "clicked", 0.01)),
    ):
        result = agent.run("Abra a conversa com Mike")
    assert result.status == "success"
    assert result.steps_taken == 1
    assert "Mike" in result.summary


def test_screen_agent_stops_on_accessible_anti_bot_challenge_before_deciding():
    capture = _capture()
    agent = ScreenAgent(abort_controller=_NoopAbort())
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[{"name": "I'm not a robot"}]),
        patch("actions.screen_control.agent.bring_to_front", return_value=True),
        patch("actions.screen_control.agent.time.sleep"),
        patch("actions.screen_control.agent.decide_next_action") as decide,
        patch("actions.screen_control.agent.execute") as execute,
    ):
        result = agent.run("Pesquise no navegador sobre o clima", window_title="Google Chrome")
    assert result.status == "blocked"
    assert "anti-robô" in result.summary
    decide.assert_not_called()
    execute.assert_not_called()


def test_screen_agent_stops_when_vision_identifies_anti_bot_challenge():
    capture = _capture()
    agent = ScreenAgent(abort_controller=_NoopAbort())
    click = ScreenAction(
        ActionType.CLICK,
        observation="A página mostra uma verificação reCAPTCHA.",
        target_description="Não sou um robô",
        x=500,
        y=500,
    )
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.bring_to_front", return_value=True),
        patch("actions.screen_control.agent.time.sleep"),
        patch("actions.screen_control.agent.decide_next_action", return_value=click),
        patch("actions.screen_control.agent.execute") as execute,
    ):
        result = agent.run("Pesquise no navegador sobre o clima", window_title="Google Chrome")
    assert result.status == "blocked"
    assert "anti-robô" in result.summary
    execute.assert_not_called()


def test_screen_tool_waits_for_manual_challenge_resolution_and_retries_once():
    import asyncio
    from actions.screen_control.agent import ScreenRunResult
    from tools import screen_control

    class FakeAgent:
        def __init__(self):
            self.results = iter((
                ScreenRunResult("blocked", "Resolva manualmente.", 0, "one"),
                ScreenRunResult("success", "A pesquisa foi concluída.", 2, "two"),
            ))
            self.calls = []

        def run(self, objective, **kwargs):
            self.calls.append((objective, kwargs))
            return next(self.results)

    class FakeClient:
        def __init__(self):
            self.waited = 0

        def wait_for_manual_browser_resolution(self):
            self.waited += 1
            return True

    fake_agent = FakeAgent()
    client = FakeClient()
    context = SimpleNamespace(client=client)
    with (
        patch("actions.screen_control.ScreenAgent", return_value=fake_agent),
        patch("core.computer_control_preferences.load_direct_computer_control", return_value=True),
    ):
        result = asyncio.run(screen_control.execute(context, {"action": "act", "objective": "Pesquise no navegador"}))

    assert result["status"] == "success"
    assert fake_agent.calls[0][0] == fake_agent.calls[1][0] == "Pesquise no navegador"
    assert client.waited == 1


def test_screen_agent_launches_named_app_then_focuses_before_interacting():
    capture = _capture()
    agent = ScreenAgent(
        config=ScreenConfig(max_steps=2, max_seconds=10, settle_delay=0.1, focus_delay=1.2),
        abort_controller=_NoopAbort(),
    )
    done = ScreenAction(ActionType.DONE, summary="A tarefa no Spotify foi concluída.")
    with (
        patch("actions.screen_control.agent.bring_to_front", side_effect=[False, False, True]) as focus,
        patch("actions.open_app.open_app", return_value="Opened Spotify.") as launch,
        patch("actions.screen_control.agent.time.sleep") as sleep,
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action", return_value=done),
    ):
        result = agent.run("Reproduza a faixa solicitada", window_title="Spotify")

    assert result.status == "success"
    launch.assert_called_once_with({"app_name": "Spotify"})
    assert focus.call_count == 3
    sleep.assert_any_call(1.2)


def test_screen_agent_does_not_act_on_wrong_window_if_requested_app_cannot_open():
    agent = ScreenAgent(abort_controller=_NoopAbort())
    with (
        patch("actions.screen_control.agent.bring_to_front", return_value=False),
        patch("actions.open_app.open_app", return_value="Could not confirm that Spotify launched."),
        patch("actions.screen_control.agent.capture_active_window") as capture,
    ):
        result = agent.run("Reproduza a faixa solicitada", window_title="Spotify")

    assert result.status == "fail"
    assert "abrir e focar" in result.summary
    capture.assert_not_called()


def test_screen_agent_never_opens_or_focuses_a_requested_terminal():
    agent = ScreenAgent(abort_controller=_NoopAbort())
    with (
        patch("actions.screen_control.agent.bring_to_front") as focus,
        patch("actions.open_app.open_app") as launch,
        patch("actions.screen_control.agent.capture_active_window") as capture,
    ):
        result = agent.run("Digite um comando", window_title="PowerShell")

    assert result.status == "fail"
    assert "terminal é protegido" in result.summary
    focus.assert_not_called()
    launch.assert_not_called()
    capture.assert_not_called()


def test_screen_agent_stops_repeating_an_unchanged_click():
    capture = _capture()
    agent = ScreenAgent(
        config=ScreenConfig(max_steps=8, max_seconds=10, settle_delay=0.1),
        abort_controller=_NoopAbort(),
    )
    click = ScreenAction(ActionType.CLICK, target_description="Mike", x=300, y=400)
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action", side_effect=[click, click, click]),
        patch("actions.screen_control.agent.execute", return_value=ActionResult(True, "clicked", 0.01)),
    ):
        result = agent.run("Abra a conversa com Mike")
    assert result.status == "fail"
    assert "três tentativas" in result.summary
    assert result.steps_taken == 3


def test_screen_agent_stops_after_configured_action_limit():
    capture = _capture()
    agent = ScreenAgent(
        config=ScreenConfig(max_steps=1, max_seconds=10, settle_delay=0.1),
        abort_controller=_NoopAbort(),
    )
    click = ScreenAction(ActionType.CLICK, target_description="Abrir resultado", x=300, y=400)
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture) as capture_window,
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action", return_value=click),
        patch("actions.screen_control.agent.execute", return_value=ActionResult(True, "clicked", 0.01)) as execute,
        patch("actions.screen_control.agent.time.sleep"),
    ):
        result = agent.run("Abra o resultado solicitado")
    assert result.status == "fail"
    assert "limite de 1 ações" in result.summary
    assert result.steps_taken == 1
    assert capture_window.call_count == 2
    execute.assert_called_once()


def test_screen_agent_checks_time_limit_before_capturing_or_acting():
    agent = ScreenAgent(
        config=ScreenConfig(max_steps=4, max_seconds=5),
        abort_controller=_NoopAbort(),
    )
    with (
        patch("actions.screen_control.agent.time.monotonic", side_effect=[100.0, 106.0]),
        patch("actions.screen_control.agent.capture_active_window") as capture_window,
        patch("actions.screen_control.agent.decide_next_action") as decide,
        patch("actions.screen_control.agent.execute") as execute,
    ):
        result = agent.run("Abra o resultado solicitado")
    assert result.status == "fail"
    assert "limite de tempo" in result.summary
    assert result.steps_taken == 0
    capture_window.assert_not_called()
    decide.assert_not_called()
    execute.assert_not_called()


def test_sensitive_file_share_is_held_before_any_action():
    capture = _capture()
    agent = ScreenAgent(
        config=ScreenConfig(max_steps=4, max_seconds=10),
        abort_controller=_NoopAbort(),
    )
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action") as decide,
    ):
        result = agent.run("Compartilhe C:\\workspace\\service\\.env com a equipe")
    assert result.status == "ask_user"
    assert "confirma" in result.summary.casefold()
    decide.assert_not_called()


def test_sensitive_file_share_continues_only_after_explicit_confirmation():
    capture = _capture()
    confirm = Mock(return_value=True)
    agent = ScreenAgent(abort_controller=_NoopAbort())
    done = ScreenAction(ActionType.DONE, summary="O arquivo foi compartilhado.")
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action", return_value=done),
        patch("actions.screen_control.agent.time.sleep"),
    ):
        result = agent.run(
            "Compartilhe C:\\workspace\\.env com a equipe",
            confirm_sensitive_share=confirm,
        )
    assert result.status == "success"
    confirm.assert_called_once()


def test_sensitive_file_share_stops_when_confirmation_is_declined():
    capture = _capture()
    confirm = Mock(return_value=False)
    agent = ScreenAgent(abort_controller=_NoopAbort())
    with (
        patch("actions.screen_control.agent.capture_active_window", return_value=capture),
        patch("actions.screen_control.agent.describe_controls", return_value=[]),
        patch("actions.screen_control.agent.decide_next_action") as decide,
        patch("actions.screen_control.agent.execute") as execute,
    ):
        result = agent.run(
            "Compartilhe C:\\workspace\\.env com a equipe",
            confirm_sensitive_share=confirm,
        )
    assert result.status == "aborted"
    confirm.assert_called_once()
    decide.assert_not_called()
    execute.assert_not_called()


def test_screen_tool_registry_exposes_local_screen_control():
    from tools.registry import registry

    declarations = registry.declarations()
    tool = next(item for item in declarations if item["name"] == "screen_control")
    assert tool["parameters"]["properties"]["action"]["enum"] == ["inspect", "act"]


def test_windows_message_flow_uses_screen_agent_and_reports_verified_send():
    import actions.send_message as send_message
    from actions.screen_control.agent import ScreenRunResult

    outcome = ScreenRunResult("success", "A mensagem aparece na conversa.", 4, "screen-run")
    with (
        patch.object(send_message.sys, "platform", "win32"),
        patch("actions.screen_control.window.bring_to_front", return_value=True),
        patch("actions.screen_control.agent.ScreenAgent") as agent_type,
    ):
        agent_type.return_value.run.return_value = outcome
        result = send_message._visual_chat_send("Discord", "Mike", "Te vejo às 18h.")

    assert "verified on screen" in result
    call = agent_type.return_value.run.call_args
    assert call.kwargs["allow_sensitive_share"] is True
    assert "Discord" in call.args[0] and "Mike" in call.args[0] and "Te vejo às 18h." in call.args[0]
