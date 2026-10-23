"""Bounded observe-decide-act-verify screen agent."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from actions.screen_control.accessibility import describe_controls
from actions.screen_control.actions import ActionResult, execute
from actions.screen_control.capture import Capture, capture_active_window
from actions.screen_control.config import ScreenConfig
from actions.screen_control.safety import (
    AbortController,
    is_blocked_terminal_target,
    sensitive_file_reason,
)
from actions.screen_control.schemas import ActionType, ScreenAction
from actions.screen_control.vision import decide_next_action, describe_screen
from actions.screen_control.window import bring_to_front


_APP_TARGETS = (
    ("Google Chrome", ("google chrome", "chrome")),
    ("Microsoft Edge", ("microsoft edge", "edge")),
    ("Firefox", ("firefox",)),
    ("Brave Browser", ("brave browser", "brave")),
    ("Opera", ("opera",)),
    ("Safari", ("safari",)),
    ("Spotify", ("spotify",)),
    ("WhatsApp", ("whatsapp", "whats app")),
    ("Discord", ("discord",)),
    ("Telegram", ("telegram",)),
    ("Slack", ("slack",)),
    ("Zoom", ("zoom",)),
    ("Microsoft Teams", ("microsoft teams", "teams")),
    ("Signal", ("signal",)),
    ("VLC", ("vlc",)),
    ("Visual Studio Code", ("visual studio code", "vs code", "vscode")),
    ("Notion", ("notion",)),
    ("Obsidian", ("obsidian",)),
    ("Steam", ("steam",)),
    ("Epic Games Launcher", ("epic games", "epic")),
    ("Microsoft Word", ("microsoft word", "word")),
    ("Microsoft Excel", ("microsoft excel", "excel")),
    ("Microsoft PowerPoint", ("microsoft powerpoint", "powerpoint")),
    ("File Explorer", ("file explorer", "explorer", "explorador de arquivos", "gerenciador de arquivos")),
    ("Calculator", ("calculator", "calculadora")),
    ("Notepad", ("notepad", "bloco de notas")),
)
_BROWSER_CUES = ("browser", "web", "internet", "navegador", "google")


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def infer_window_title(objective: str) -> str:
    """Infer a common app target when a caller omits `window_title`."""
    folded = _fold_text(objective)
    mentions: list[tuple[int, int, str]] = []
    for title, aliases in _APP_TARGETS:
        for alias in aliases:
            match = re.search(rf"(?<![a-z0-9]){re.escape(_fold_text(alias))}(?![a-z0-9])", folded)
            if match:
                mentions.append((match.start(), -len(alias), title))
                break
    if mentions:
        title = min(mentions)[2]
        if title in {"Google Chrome", "Microsoft Edge", "Firefox", "Brave Browser", "Opera", "Safari"}:
            try:
                from actions.browser_control import browser_window_title
                return browser_window_title(title)
            except Exception:
                pass
        return title

    # Generic browser requests use the installed system default, not a hard-coded browser.
    if any(re.search(rf"(?<![a-z0-9]){re.escape(cue)}(?![a-z0-9])", folded) for cue in _BROWSER_CUES):
        try:
            from actions.browser_control import browser_window_title
            return browser_window_title()
        except Exception:
            return "Microsoft Edge"
    return ""


def _explicit_browser_search(objective: str, window_title: str, process_name: str) -> bool:
    if not re.search(
        r"\b(?:search|searching|look\s+up|google|pesquis(?:e|ar|a|ando)|busc(?:a|ar|e|ando)|busque|procure|procurar)\b",
        _fold_text(objective),
    ):
        return False
    browser = _fold_text(f"{window_title} {process_name}")
    return any(name in browser for name in (
        "chrome", "edge", "firefox", "brave", "opera", "safari", "browser", "navegador",
    ))


@dataclass(frozen=True)
class ScreenRunResult:
    status: str
    summary: str
    steps_taken: int = 0
    run_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _share_intent(goal: str) -> bool:
    text = str(goal or "").casefold()
    explicit_share = any(word in text for word in ("share", "upload", "attach", "compartilhar", "compartilhe", "compartilha", "anexar", "anexe"))
    file_target = any(word in text for word in ("file", "arquivo", "attachment", "anexo", "dockerfile", "docker-compose", "docker config", "configuração docker", "credential", "credencial", "secret", "segredo", "private key", "chave privada", ".env"))
    explicit_send_file = bool(re.search(
        r"\b(?:send|enviar|envie|mandar|mande)\b.{0,24}\b(?:file|arquivo|dockerfile|docker-compose|\.env|credencial|credential|chave|key)\b",
        text,
    ))
    sensitive_file_ref = bool(re.search(
        r"(?i)(?:\.env(?:\.[A-Za-z0-9_.-]+)?|docker-compose(?:\.[A-Za-z0-9_.-]+)?|dockerfile|credentials?|secrets?|private[-_ ]?key|id_rsa|id_ed25519)",
        text,
    ))
    return (explicit_share and (file_target or sensitive_file_ref)) or explicit_send_file or (sensitive_file_ref and any(word in text for word in ("send", "enviar", "envie", "mandar", "mande")))


def _anti_bot_verification_visible(window_title: str, process_name: str, controls: list) -> bool:
    labels = [str(window_title or ""), str(process_name or "")]
    for control in controls:
        if isinstance(control, dict):
            labels.append(str(control.get("name", "") or ""))
        else:
            labels.append(str(getattr(control, "name", "") or ""))
    visible_text = _fold_text(" ".join(labels))
    return any(marker in visible_text for marker in (
        "unusual traffic from your computer network",
        "our systems have detected unusual traffic",
        "consultas automatizadas",
        "tráfego incomum",
        "i am not a robot",
        "im not a robot",
        "verify you are human",
        "captcha",
    ))


def _sensitive_visible_file(goal: str, controls: list) -> tuple[str, str] | None:
    sensitive_names = re.findall(
        r"(?i)(?:\.env(?:\.[A-Za-z0-9_.-]+)?|docker-compose(?:\.[A-Za-z0-9_.-]+)?|"
        r"dockerfile|credentials?(?:\.[A-Za-z0-9_.-]+)?|secrets?(?:\.[A-Za-z0-9_.-]+)?|"
        r"id_rsa|id_ed25519|[A-Za-z0-9_.-]*private[-_ ]?key[A-Za-z0-9_.-]*)",
        str(goal or ""),
    )
    if _share_intent(goal):
        for name in sensitive_names:
            reason = sensitive_file_reason(name)
            if reason:
                return name, reason
    # A full path supplied by the user allows checking small text/config files locally.
    goal_text = str(goal or "")
    quoted_paths = re.findall(r"['\"]((?:[A-Za-z]:\\|/)[^'\"]+)['\"]", goal_text)
    paths = quoted_paths + re.findall(r"(?:[A-Za-z]:\\|/)[^\s\r\n\"<>|?*]+", goal_text)
    for candidate in paths:
        reason = sensitive_file_reason(candidate.strip().rstrip(".,;:"))
        if reason:
            return Path(candidate.strip().rstrip(".,;:")).name, reason
    if _share_intent(goal):
        for control in controls:
            name = str(getattr(control, "name", "") or (control.get("name", "") if isinstance(control, dict) else ""))
            selected = bool(getattr(control, "selected", False) or (control.get("selected", False) if isinstance(control, dict) else False))
            if not selected:
                continue
            reason = sensitive_file_reason(name)
            if reason:
                return name, reason
    return None


class ScreenAgent:
    def __init__(self, *, config: ScreenConfig | None = None, vision_client=None, abort_controller=None):
        self.config = config or ScreenConfig.from_env()
        self.vision_client = vision_client
        self.abort_controller = abort_controller or AbortController(self.config.kill_switch_hotkey)

    def inspect(self) -> str:
        capture = capture_active_window(self.config.max_image_side)
        controls = describe_controls(capture.window)
        return describe_screen(
            capture, controls, model=self.config.vision_model, client=self.vision_client
        )

    def _focus_or_launch(self, window_title: str, *, deadline: float) -> bool:
        if is_blocked_terminal_target(window_title):
            return False
        if bring_to_front(window_title):
            return True

        from actions.open_app import open_app

        launch_result = open_app({"app_name": window_title})
        if not launch_result.startswith("Opened "):
            return False
        while time.monotonic() < deadline:
            if self.abort_controller.aborted:
                return False
            if bring_to_front(window_title):
                return True
            time.sleep(0.4)
        return False

    def run(self, objective: str, *, window_title: str = "", allow_sensitive_share: bool = False) -> ScreenRunResult:
        goal = " ".join(str(objective or "").split())
        window_title = str(window_title or "").strip() or infer_window_title(goal)
        run_id = uuid.uuid4().hex[:12]
        if not goal:
            return ScreenRunResult("fail", "Diga o que devo fazer na tela.", 0, run_id)
        if window_title and is_blocked_terminal_target(window_title):
            return ScreenRunResult(
                "fail",
                "O terminal é protegido e não pode ser alvo do controle de tela. Peça a abertura do aplicativo pelo nome.",
                0,
                run_id,
            )
        started = time.monotonic()
        history: list[dict] = []
        previous_hash = ""
        repeated_unchanged: dict[str, int] = {}
        self.abort_controller.start()
        logging.getLogger("argus.screen").info(
            "screen_run_started",
            extra={"screen_run_id": run_id, "objective_chars": len(goal)},
        )
        try:
            if window_title:
                if not self._focus_or_launch(window_title, deadline=time.monotonic() + 12.0):
                    if self.abort_controller.aborted:
                        return ScreenRunResult("aborted", "Interrompi a abertura do aplicativo pelo atalho de emergência.", 0, run_id)
                    return ScreenRunResult("fail", f"Não consegui abrir e focar a janela de {window_title!r}.", 0, run_id)
                time.sleep(self.config.focus_delay)

            for step in range(1, self.config.max_steps + 1):
                if self.abort_controller.aborted:
                    return ScreenRunResult("aborted", "Interrompi o controle da tela pelo atalho de emergência.", step - 1, run_id)
                if time.monotonic() - started > self.config.max_seconds:
                    return ScreenRunResult("fail", "O controle da tela excedeu o limite de tempo.", step - 1, run_id)

                capture = capture_active_window(self.config.max_image_side)
                controls = describe_controls(capture.window)
                file_risk = _sensitive_visible_file(goal, controls)
                if file_risk and not allow_sensitive_share:
                    name, reason = file_risk
                    return ScreenRunResult(
                        "ask_user",
                        f"O arquivo {name!r} parece ser {reason}. Confirma que devo compartilhá-lo?",
                        step - 1,
                        run_id,
                    )
                if _anti_bot_verification_visible(
                    capture.window.title, capture.window.process_name, controls
                ):
                    return ScreenRunResult(
                        "fail",
                        "A página apresentou uma verificação anti-robô. Parei sem interagir, repetir a busca ou tentar contorná-la.",
                        step - 1,
                        run_id,
                    )

                screenshot_hash = hashlib.sha256(capture.image_bytes).hexdigest()
                try:
                    decision = decide_next_action(
                        capture, goal, history, controls,
                        model=self.config.vision_model,
                        client=self.vision_client,
                    )
                except Exception as exc:
                    return ScreenRunResult("fail", f"Não consegui decidir a próxima ação na tela: {exc}", step - 1, run_id)

                if decision.action == ActionType.DONE:
                    summary = decision.summary or "Concluí o pedido e confirmei o resultado na tela."
                    return ScreenRunResult("success", summary, step - 1, run_id)
                if decision.action == ActionType.FAIL:
                    return ScreenRunResult("fail", decision.summary or "Não consegui concluir o pedido na tela.", step - 1, run_id)
                if decision.action == ActionType.ASK_USER:
                    return ScreenRunResult("ask_user", decision.summary or "Preciso esclarecer qual item você quer.", step - 1, run_id)
                if self.config.dry_run:
                    return ScreenRunResult(
                        "dry_run",
                        f"Prévia: {decision.action.value} — {decision.target_description or decision.evidence or decision.observation}",
                        step - 1,
                        run_id,
                    )

                result = execute(
                    decision,
                    capture,
                    mouse_duration=self.config.mouse_move_duration,
                    allow_browser_search=_explicit_browser_search(
                        goal, capture.window.title, capture.window.process_name
                    ),
                )
                time.sleep(self.config.settle_delay)
                after = capture_active_window(self.config.max_image_side)
                after_hash = hashlib.sha256(after.image_bytes).hexdigest()
                signature = json.dumps({
                    "action": decision.action.value, "target": decision.target_description,
                    "x": decision.x, "y": decision.y,
                }, sort_keys=True, ensure_ascii=False)
                if result.ok and screenshot_hash == after_hash:
                    repeated_unchanged[signature] = repeated_unchanged.get(signature, 0) + 1
                else:
                    repeated_unchanged[signature] = 0
                history.append({
                    "step": step,
                    "observation": decision.observation,
                    "evidence": decision.evidence,
                    "action": decision.action.value,
                    "target": decision.target_description,
                    "coordinates": [decision.x, decision.y] if decision.x is not None else None,
                    "result": result.detail,
                    "ok": result.ok,
                    "screen_changed": screenshot_hash != after_hash,
                    "duration_seconds": round(result.duration, 3),
                })
                logging.getLogger("argus.screen").info(
                    "screen_step_completed",
                    extra={
                        "screen_run_id": run_id,
                        "step": step,
                        "action": decision.action.value,
                        "ok": result.ok,
                        "screen_changed": screenshot_hash != after_hash,
                        "duration_seconds": round(result.duration, 3),
                    },
                )
                self._write_step_debug(run_id, step, after, decision)
                if repeated_unchanged.get(signature, 0) >= 3:
                    return ScreenRunResult("fail", "A tela não mudou após três tentativas no mesmo alvo; interrompi para evitar um loop.", step, run_id)
            return ScreenRunResult("fail", f"A tarefa atingiu o limite de {self.config.max_steps} ações sem confirmação de sucesso.", self.config.max_steps, run_id)
        finally:
            self.abort_controller.stop()

    def _write_step_debug(self, run_id: str, step: int, capture: Capture, action: ScreenAction) -> None:
        if not self.config.debug_screenshots:
            return
        try:
            from PIL import Image, ImageDraw
            root = Path(__file__).resolve().parents[2] / "logs" / "screen" / run_id
            root.mkdir(parents=True, exist_ok=True)
            image = Image.open(__import__("io").BytesIO(capture.image_bytes)).convert("RGB")
            if action.x is not None and action.y is not None:
                point = (round(action.x * image.width / 1000), round(action.y * image.height / 1000))
                draw = ImageDraw.Draw(image)
                radius = max(6, image.width // 90)
                draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), outline="red", width=3)
            image.save(root / f"step-{step:02d}.png")
        except Exception as exc:
            print(f"[ScreenAgent] screenshot debug save failed: {exc}")
