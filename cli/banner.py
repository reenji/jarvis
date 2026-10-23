"""Brand assets for the ARGUS terminal interface."""

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
