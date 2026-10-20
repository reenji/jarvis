"""Non-mutating repository checks used by the QA runner."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from core.qa_report import Finding


EXPECTED_TOOLS = {
    "open_app", "web_search", "weather_report", "check_messages",
    "prepare_message_reply", "send_message", "email_control", "reminder", "youtube_video", "media_control",
    "screen_process", "computer_settings", "browser_control", "file_controller",
    "desktop_control", "code_helper", "dev_agent", "agent_task",
    "computer_control", "screen_control", "game_updater", "flight_finder", "argus_ui_control",
    "file_processor", "create_presentation", "deep_research", "graphics_quality", "task_status", "save_memory",
}


def declared_tools(main_path: Path) -> list[str]:
    """Get declared tool names from the tool registry.

    Falls back to AST parsing of main.py for backward compatibility.
    """
    # Try to get from registry first (new architecture)
    try:
        # Add project root to path if needed
        project_root = main_path.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from tools.registry import registry
        registry._internal_discover()
        return sorted(registry._declarations.keys())
    except Exception:
        pass

    # Fallback: parse main.py for TOOL_DECLARATIONS (old architecture)
    tree = ast.parse(main_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "TOOL_DECLARATIONS" for target in node.targets):
            continue
        names = []
        for item in getattr(node.value, "elts", []):
            if not isinstance(item, ast.Dict):
                continue
            for key, value in zip(item.keys, item.values):
                if isinstance(key, ast.Constant) and key.value == "name" and isinstance(value, ast.Constant):
                    names.append(str(value.value))
        return names
    return []


def repository_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    main_path = root / "main.py"
    ui_path = root / "ui"
    ui_sources = sorted(ui_path.rglob("*.py")) if ui_path.is_dir() else []
    tools = declared_tools(main_path)
    missing = sorted(EXPECTED_TOOLS - set(tools))
    duplicates = sorted({name for name in tools if tools.count(name) > 1})
    main_source = main_path.read_text(encoding="utf-8")

    if missing or duplicates:
        findings.append(Finding(
            "P0", "Tool declaration contract is inconsistent", "Tool routing",
            "Gemini can request a missing or ambiguous tool handler.",
            "Run the automated contract audit.",
            "Every supported tool is declared exactly once.",
            f"Missing={missing}; duplicates={duplicates}",
        ))
    unhandled = sorted(name for name in tools if f'name == "{name}"' not in main_source)
    if unhandled:
        findings.append(Finding(
            "P0", "Declared tools lack dispatch branches", "Tool routing",
            "A valid Live tool call can return no useful result.",
            "Compare TOOL_DECLARATIONS with ArgusLive._execute_tool.",
            "Every declaration has an execution path.",
            f"Unhandled={unhandled}",
        ))

    exception_count = 0
    for path in [main_path, *ui_sources, *sorted((root / "actions").glob("*.py"))]:
        source = path.read_text(encoding="utf-8", errors="replace")
        exception_count += len(re.findall(r"except Exception(?:\s+as\s+\w+)?:", source))
    if exception_count >= 100:
        findings.append(Finding(
            "P2", "Broad exception handling reduces failure visibility", "Observability",
            "Real integration failures may be swallowed or reduced to generic UI messages.",
            "Trigger mocked permission, network, and subprocess failures and inspect structured logs.",
            "Failures retain actionable context and are observable in QA reports.",
            f"Found {exception_count} broad Exception handlers in runtime modules.",
        ))

    deprecated_sdk_files = []
    for path in [main_path, *sorted((root / "actions").glob("*.py")), *sorted((root / "agent").glob("*.py"))]:
        if "google.generativeai" in path.read_text(encoding="utf-8", errors="replace"):
            deprecated_sdk_files.append(str(path.relative_to(root)))
    if deprecated_sdk_files:
        findings.append(Finding(
            "P2", "Deprecated Gemini SDK remains in runtime paths", "Dependencies",
            "Those integrations no longer receive fixes and may break as Gemini APIs evolve.",
            "Run the unit suite and exercise tools importing google.generativeai.",
            "Runtime integrations consistently use the supported google.genai SDK.",
            "Affected files: " + ", ".join(deprecated_sdk_files),
        ))

    token_path = ui_path / "theme" / "tokens.py"
    color_literals = []
    for path in ui_sources:
        if path == token_path:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"#[0-9A-Fa-f]{3,8}\b", line):
                color_literals.append(f"{path.relative_to(root)}:{line_number}")
    if color_literals:
        findings.append(Finding(
            "P1", "UI colors must come from the central token module", "Theming",
            "A color literal outside ui/theme/tokens.py can drift from the shared palette.",
            "Replace the literal with a semantic token and rerun the package audit.",
            "No hexadecimal color literals exist outside ui/theme/tokens.py.",
            f"Found {len(color_literals)} literals at: {', '.join(color_literals)}",
        ))

    rgba_literals = []
    ui_imports = []
    for path in ui_sources:
        if path == token_path:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        relative = str(path.relative_to(root))
        for line_number, line in enumerate(source.splitlines(), 1):
            if re.search(r"\brgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+", line, re.IGNORECASE):
                rgba_literals.append(f"{relative}:{line_number}")
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Call) and node.args:
                function = node.func
                dynamic_import = (
                    isinstance(function, ast.Name) and function.id == "__import__"
                ) or (
                    isinstance(function, ast.Attribute)
                    and function.attr == "import_module"
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "importlib"
                )
                if dynamic_import and isinstance(node.args[0], ast.Constant):
                    modules = [str(node.args[0].value)]
            if any(
                module == "actions" or module.startswith("actions.")
                or module == "google" or module.startswith("google.")
                for module in modules
            ):
                ui_imports.append(f"{relative}:{getattr(node, 'lineno', 1)}")

    if rgba_literals:
        findings.append(Finding(
            "P1", "UI alpha colors must come from central opacity tokens", "Theming",
            "Numeric RGB/RGBA literals outside the token module can drift from the shared palette.",
            "Use a semantic palette color with qss_rgba and a named opacity token.",
            "No numeric RGB/RGBA literals exist outside ui/theme/tokens.py.",
            f"Found {len(rgba_literals)} literals at: {', '.join(rgba_literals)}",
        ))
    if ui_imports:
        findings.append(Finding(
            "P1", "UI modules cross the engine or vendor dependency boundary", "Architecture",
            "UI modules importing action or Gemini packages couple presentation code to runtime services.",
            "Move shared data to a neutral module or inject application-owned services.",
            "No UI module imports actions or google packages.",
            "Imports at: " + ", ".join(ui_imports),
        ))
    return findings
