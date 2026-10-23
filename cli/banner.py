"""Brand assets for the ARGUS terminal interface."""

import os
import sys

EYE_BANNER = r"""
        .-=================-.
     .-'                     '-.
   .'       .-----------.       '.
  /       .'             '.       \
 |       /     .---.       \       |
 |      |     /  o  \       |      |
 |       \    '---'       /       |
  \       '.           .'       /
   '.       '---------'       .'
     '-.                   .-'
        '-================-'
""".strip("\n")


def banner_details() -> tuple[str, str]:
    """Return the installed ARGUS version and currently configured model."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        package_version = version("argus-mark-xxxix")
    except PackageNotFoundError:
        package_version = "0.1.0"

    try:
        from config.settings import get_settings

        model = get_settings().llm.model
    except Exception:
        model = "model not configured"
    return package_version, model


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "on", "1", "sim", "s"}:
            return True
        if normalized in {"false", "no", "off", "0", "nao", "não", "n"}:
            return False
    return None


def banner_preference() -> bool:
    """Resolve the banner preference from environment, then user config."""
    env_value = os.environ.get("ARGUS_CLI_BANNER")
    if env_value is not None:
        parsed = _parse_bool(env_value)
        if parsed is not None:
            return parsed

    try:
        from config.user_config import load_user_config

        configured = _parse_bool(load_user_config().get("banner"))
    except Exception:
        configured = None
    return configured if configured is not None else True


def should_show_banner(*, no_banner: bool = False, stdin=None, stdout=None) -> bool:
    """Show the brand only for interactive terminals unless it is disabled."""
    if no_banner:
        return False
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    try:
        if not input_stream.isatty() or not output_stream.isatty():
            return False
    except (AttributeError, OSError):
        return False
    return banner_preference()
