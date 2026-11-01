from __future__ import annotations

from typing import Any, Awaitable, Callable


async def execute(ctx: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Adapter layer.

    For now, tools are thin wrappers over the existing action functions
    still implemented in `actions/` and helpers.

    This keeps Fase 4 incremental and lets us preserve behavior.
    """

    # Most tools map 1:1 to a specific action function.
    # We keep this mapping centralized to avoid editing main.py for each tool.
    mapping: dict[str, tuple[str, str]] = {
        "open_app": ("actions.open_app", "open_app"),
        "weather_report": ("actions.weather_report", "weather_action"),
        "web_search": ("actions.web_search", "web_search"),
        "deep_research": ("actions.deep_research", "request_deep_research"),
        "create_presentation": ("actions.presentation_maker", "request_presentation"),
        "flight_finder": ("actions.flight_finder", "flight_finder"),
        "youtube_video": ("actions.youtube_video", "youtube_video"),
        "media_control": ("actions.media_control", "media_control"),
        "computer_settings": ("actions.computer_settings", "computer_settings"),
        "computer_control": ("actions.computer_control", "computer_control"),
        "desktop_control": ("actions.desktop", "desktop_control"),
        "browser_control": ("actions.browser_control", "browser_control"),
        "file_controller": ("actions.file_controller", "file_controller"),
        "file_processor": ("actions.file_processor", "file_processor"),
        "code_helper": ("actions.code_helper", "code_helper"),
        "dev_agent": ("actions.dev_agent", "dev_agent"),
        "game_updater": ("actions.game_updater", "game_updater"),
        "check_messages": ("actions.message_monitor", "check_messages"),
        "prepare_message_reply": ("actions.send_message", "prepare_message_reply"),
        "send_message": ("actions.send_message", "send_message"),
        "email_control": ("actions.email_control", "email_control"),
        "reminder": ("actions.reminder", "reminder"),
        "screen_process": ("actions.screen_processor", "screen_process"),
        "task_status": ("agent.task_queue", "task_status"),
        "graphics_quality": ("main", "set_graphics_quality_stub"),
        "argus_ui_control": ("main", "argus_ui_control_stub"),
        "save_memory": ("memory.memory_manager", "save_memory_stub"),
        "save_memory": ("memory.memory_manager", "update_memory_stub"),
        "computer_settings": ("actions.computer_settings", "computer_settings"),
        "desktop_control": ("actions.desktop", "desktop_control"),
        "agent_task": ("agent.task_queue", "agent_task_submit"),
        "task_status": ("agent.task_queue", "task_status_get"),
    }

    # Temporarily: we route by calling the existing actions directly with
    # the same signature main.py uses. For tools not yet mapped here,
    # raise a clear error.

    if name == "graphics_quality":
        quality = (args.get("quality") or "").strip().lower()
        set_quality = getattr(ctx.client, "set_graphics_quality", None)
        if not callable(set_quality):
            return {"result": "Graphics quality controls are unavailable for this client."}
        set_quality(quality)
        return {"result": f"ARGUS graphics quality changed to {quality}."}

    if name == "argus_ui_control":
        action = str(args.get("action") or "").strip().lower()
        if action == "change_theme":
            theme = str(args.get("theme") or "").strip().lower()
            allowed = {"arc_reactor", "stealth_red", "vibranium_purple", "nanotech_gold", "platinum"}
            if theme not in allowed:
                raise ValueError(f"Unknown ARGUS theme: {theme or 'missing'}")
            set_theme = getattr(ctx.client, "set_theme", None)
            if not callable(set_theme):
                return {"result": "Theme controls are unavailable for this client."}
            set_theme(theme)
            return {"result": f"ARGUS theme changed to {theme.replace('_', ' ')}."}
        if action == "change_graphics_quality":
            quality = str(args.get("graphics_quality") or "").strip().lower()
            if quality not in {"low", "medium", "high"}:
                raise ValueError(f"Unknown graphics quality: {quality or 'missing'}")
            set_quality = getattr(ctx.client, "set_graphics_quality", None)
            if not callable(set_quality):
                return {"result": "Graphics quality controls are unavailable for this client."}
            set_quality(quality)
            return {"result": f"ARGUS graphics quality changed to {quality}."}
        handle_command = getattr(ctx.client, "handle_ui_command", None)
        if not callable(handle_command):
            return {"result": "Interface controls are unavailable for this client."}
        handle_command(action)
        return {"result": f"ARGUS interface action completed: {action.replace('_', ' ')}."}

    if name == "save_memory":
        # main.py special-cases save_memory to update long-term memory silently
        from memory.memory_manager import update_memory

        category = args.get("category", "notes")
        key = args.get("key", "")
        value = args.get("value", "")
        if key and value:
            update_memory({category: {key: {"value": value}}})
        if not getattr(ctx.client, "muted", False):
            ctx.client.set_state("LISTENING")
        return {"result": "ok", "silent": True}

    # General mappings: call the action functions.
    # These calls should mirror main.py's branches as closely as possible.
    if name == "open_app":
        from actions.open_app import open_app
        r = open_app(parameters=args, response=None, player=ctx.client)
        return {"result": r or f"Opened {args.get('app_name')}."}

    if name == "weather_report":
        from actions.weather_report import weather_action
        r = weather_action(parameters=args, player=ctx.client)
        return {"result": r or "Weather delivered."}

    if name == "browser_control":
        from actions.browser_control import browser_control
        r = browser_control(parameters=args, player=ctx.client)
        return {"result": r or "Done."}

    if name == "file_controller":
        from actions.file_controller import file_controller
        if (str(args.get("action") or "").lower() == "open" and not args.get("path") and not args.get("name")):
            cur = getattr(ctx.client, "current_file", None)
            if cur:
                args["path"] = cur
        r = file_controller(parameters=args, player=ctx.client)
        return {"result": r or "Done."}

    if name == "check_messages":
        from actions.message_monitor import check_messages
        r = check_messages(parameters=args, response=None, player=ctx.client, session_memory=None)
        return {"result": r or "No readable messages were found."}

    if name == "prepare_message_reply":
        from actions.send_message import prepare_message_reply
        r = prepare_message_reply(parameters=args, response=None, player=ctx.client, session_memory=None)
        return {"result": r or "The message draft could not be prepared."}

    if name == "send_message":
        from actions.send_message import send_message
        r = send_message(parameters=args, response=None, player=ctx.client, session_memory=None)
        return {"result": r or f"Message sent to {args.get('receiver')}."}

    if name == "email_control":
        from actions.email_control import email_control
        if str(args.get("action") or "").lower() == "connect" and not args.get("credentials_path"):
            cur = getattr(ctx.client, "current_file", None)
            if cur and str(cur).lower().endswith(".json"):
                args["credentials_path"] = cur
        r = email_control(parameters=args, response=None, player=ctx.client, session_memory=None)
        return {"result": r or "Email action completed."}

    if name == "reminder":
        from actions.reminder import reminder
        r = reminder(parameters=args, response=None, player=ctx.client)
        return {"result": r or "Reminder set."}

    if name == "youtube_video":
        from actions.youtube_video import youtube_video
        r = youtube_video(parameters=args, response=None, player=ctx.client)
        return {"result": r or "Done."}

    if name == "media_control":
        from actions.media_control import media_control
        r = media_control(parameters=args, response=None, player=ctx.client)
        return {"result": r or "Done."}

    if name == "screen_process":
        from actions.screen_processor import screen_process
        # run in background thread like main.py
        import threading
        threading.Thread(
            target=screen_process,
            kwargs={
                "parameters": args,
                "response": None,
                "player": ctx.client,
                "session_memory": None,
                "speak": ctx.speak_vision_result,
            },
            daemon=True,
        ).start()
        return {"result": "Vision module activated. Stay completely silent — vision module will speak directly."}

    if name == "computer_settings":
        from actions.computer_settings import computer_settings
        r = computer_settings(parameters=args, response=None, player=ctx.client)
        return {"result": r or "Done."}

    if name == "desktop_control":
        from actions.desktop import desktop_control
        r = desktop_control(parameters=args, player=ctx.client)
        return {"result": r or "Done."}

    if name == "code_helper":
        from actions.code_helper import code_helper
        r = code_helper(parameters=args, player=ctx.client, speak=ctx.speak)
        return {"result": r or "Done."}

    if name == "dev_agent":
        from actions.dev_agent import dev_agent
        r = dev_agent(parameters=args, player=ctx.client, speak=ctx.speak)
        return {"result": r or "Done."}

    if name == "agent_task":
        from agent.task_queue import get_queue, TaskPriority
        priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
        priority = priority_map.get(str(args.get("priority") or "normal").lower(), TaskPriority.NORMAL)
        task_id = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=ctx.speak, immediate=True)
        return {"result": f"Task started (ID: {task_id})."}

    if name == "web_search":
        from actions.web_search import web_search
        r = web_search(parameters=args, player=ctx.client)
        return {"result": r or "Done."}

    if name == "file_processor":
        from actions.file_processor import file_processor
        current_file = getattr(ctx.client, "current_file", None)
        if not args.get("file_path") and current_file:
            args["file_path"] = current_file
        r = file_processor(parameters=args, player=ctx.client, speak=ctx.speak)
        return {"result": r or "Done."}

    if name == "computer_control":
        from actions.computer_control import computer_control
        r = computer_control(parameters=args, player=ctx.client)
        return {"result": r or "Done."}

    if name == "game_updater":
        from actions.game_updater import game_updater
        r = game_updater(parameters=args, player=ctx.client, speak=ctx.speak)
        return {"result": r or "Done."}

    if name == "flight_finder":
        from actions.flight_finder import flight_finder
        r = flight_finder(parameters=args, player=ctx.client)
        return {"result": r or "Done."}

    if name == "create_presentation":
        from actions.presentation_maker import request_presentation
        from pathlib import Path
        current_file = getattr(ctx.client, "current_file", None)
        supported_sources = {
            ".txt", ".md", ".rst", ".csv", ".json", ".jsonl", ".docx", ".pptx",
            ".pdf", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".webp",
            ".wav", ".mp3", ".m4a", ".mp4", ".mov", ".avi", ".webm",
        }
        if (
            not args.get("source_file")
            and not args.get("source_files")
            and current_file
            and Path(str(current_file)).suffix.lower() in supported_sources
        ):
            args["source_files"] = [current_file]
        r = request_presentation(parameters=args, player=ctx.client, speak=ctx.speak)
        return {"result": r or "Presentation preference requested."}

    if name == "task_status":
        from agent.task_queue import get_queue
        queue = get_queue()
        action = str(args.get("action") or "get").lower()
        task_id = str(args.get("task_id") or "").strip()
        if action == "all" or not task_id:
            import json
            return {"result": json.dumps(queue.get_all_statuses(), ensure_ascii=False)}
        if action == "cancel":
            return {"result": f"Task {task_id} cancelled." if queue.cancel(task_id) else f"Task {task_id} could not be cancelled."}
        status = queue.get_status(task_id)
        import json
        return {"result": json.dumps(status, ensure_ascii=False) if status else f"Task {task_id} was not found."}

    if name == "save_memory":
        # handled above
        raise AssertionError('unreachable')

    raise NotImplementedError(f"Tool implementation adapter missing mapping for: {name}")
