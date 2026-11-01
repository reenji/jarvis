from __future__ import annotations

import asyncio
import importlib
import pkgutil
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

import config.settings as settings_mod
from core.argus_client import ArgusClient


@dataclass(frozen=True, init=False)
class ToolContext:
    """Minimal context exposed to tools.

    Tools should treat this as read-only; any mutation/side-effects must
    happen via explicitly passed callbacks (e.g. speak).
    """

    client: ArgusClient
    speak: Callable[[str], bool]
    speak_vision_result: Callable[[str], bool]

    def __init__(
        self,
        client: ArgusClient | None = None,
        speak: Callable[[str], bool] | None = None,
        speak_vision_result: Callable[[str], bool] | None = None,
        *,
        ui: ArgusClient | None = None,
    ) -> None:
        """Accept the old ``ui=`` keyword while tools migrate to ``client``."""
        if client is not None and ui is not None:
            raise ValueError("Pass either client or ui, not both")
        adapter = client if client is not None else ui
        if adapter is None:
            raise ValueError("ToolContext requires a client")
        if speak is None or speak_vision_result is None:
            raise ValueError("ToolContext requires speak callbacks")
        object.__setattr__(self, "client", adapter)
        object.__setattr__(self, "speak", speak)
        object.__setattr__(self, "speak_vision_result", speak_vision_result)

    @property
    def ui(self) -> ArgusClient:
        """Compatibility alias for plugins using the previous context shape."""
        return self.client


ExecuteFn = Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]


class ToolRegistry:
    def __init__(self) -> None:
        self._internal: Dict[str, ExecuteFn] = {}
        self._declarations: Dict[str, dict[str, Any]] = {}
        self._plugins_loaded_for_enabled_set: Optional[frozenset[str]] = None
        self._plugin_execute: Dict[str, ExecuteFn] = {}
        self._plugin_declarations: Dict[str, dict[str, Any]] = {}

    def _internal_discover(self) -> None:
        if self._internal:
            return

        package = importlib.import_module("tools")
        for mod in pkgutil.iter_modules(package.__path__):
            if mod.name in {"registry", "impl", "__init__"}:
                continue
            module = importlib.import_module(f"tools.{mod.name}")
            decl = getattr(module, "declaration", None)
            execute_fn = getattr(module, "execute", None)
            if not decl or not isinstance(decl, dict):
                continue
            name = decl.get("name")
            if not name or not callable(execute_fn):
                continue
            # Tool modules provide async execute.
            self._internal[str(name)] = execute_fn  # type: ignore[assignment]
            self._declarations[str(name)] = decl

    def _enabled_plugins_set(self) -> frozenset[str]:
        s = settings_mod.get_settings()
        return frozenset(s.features.enabled_plugins or [])

    def _load_plugins_if_needed(self) -> None:
        enabled = self._enabled_plugins_set()
        if enabled == self._plugins_loaded_for_enabled_set:
            return

        self._plugin_execute.clear()
        self._plugin_declarations.clear()
        self._plugins_loaded_for_enabled_set = enabled

        if not enabled:
            return

        plugins_pkg = importlib.import_module("plugins")
        available = {m.name for m in pkgutil.iter_modules(plugins_pkg.__path__)}

        for plugin_name in sorted(enabled):
            if plugin_name not in available:
                continue
            module = importlib.import_module(f"plugins.{plugin_name}")
            register_fn = getattr(module, "register", None)
            if not callable(register_fn):
                raise RuntimeError(
                    f"Enabled plugin '{plugin_name}' lacks register(tool_registry)"
                )
            register_fn(self)

    def register_tool(
        self,
        *,
        name: str,
        declaration: dict[str, Any],
        execute_fn: ExecuteFn,
    ) -> None:
        if not name:
            raise ValueError("Tool name is required")
        self._plugin_execute[name] = execute_fn
        self._plugin_declarations[name] = declaration

    def declarations(
        self,
        *,
        cloud_safe: bool = False,
        cloud_safe_action_names: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        self._internal_discover()
        self._load_plugins_if_needed()

        s = settings_mod.get_settings()
        enabled_tools = set(s.features.enabled_tools or [])

        all_decls = dict(self._declarations)
        all_decls.update(self._plugin_declarations)

        names = list(all_decls.keys())
        if enabled_tools:
            names = [n for n in names if n in enabled_tools]

        if cloud_safe:
            allowed = cloud_safe_action_names or set()
            names = [n for n in names if n in allowed]

        return [all_decls[n] for n in sorted(names)]

    async def execute(
        self,
        *,
        name: str,
        ctx: ToolContext,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        self._internal_discover()
        self._load_plugins_if_needed()

        execute_fn = self._internal.get(name) or self._plugin_execute.get(name)
        if not execute_fn:
            raise KeyError(f"Tool not found: {name}")
        res = await execute_fn(ctx, args)
        return res


registry = ToolRegistry()
