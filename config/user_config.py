"""User-scoped Argus configuration and secret-storage helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from config.paths import default_argus_data_dir

KEYRING_SERVICE = "ARGUS"
KEYRING_GEMINI_USERNAME = "gemini_api_key"


class UserConfigError(ValueError):
    """Invalid or inaccessible user configuration."""


def user_config_path() -> Path:
    override = os.environ.get("ARGUS_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    return default_argus_data_dir() / "config.yaml"


def _load_yaml(text: str) -> Any:
    try:
        import yaml
    except ImportError:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise UserConfigError("YAML support is unavailable; install PyYAML to read this configuration.") from exc
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        raise UserConfigError("The Argus configuration file is not valid YAML.") from exc


def load_user_config(*, path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else user_config_path()
    if not config_path.exists():
        return {}
    try:
        value = _load_yaml(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UserConfigError(f"Could not read Argus configuration at {config_path}.") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise UserConfigError("The Argus configuration must contain a YAML mapping.")
    return value


def _dump_yaml(value: dict[str, Any]) -> str:
    try:
        import yaml
    except ImportError:
        # JSON is a valid YAML 1.2 document and can be read without PyYAML.
        return json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def save_user_config(value: dict[str, Any], *, path: str | Path | None = None) -> Path:
    config_path = Path(path) if path is not None else user_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        _secure_permissions(config_path.parent, directory=True)
        payload = _dump_yaml(value)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_path.parent,
            prefix=f".{config_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _secure_permissions(temp_path)
        os.replace(temp_path, config_path)
        _secure_permissions(config_path)
        return config_path
    except OSError as exc:
        try:
            if "temp_path" in locals():
                temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise UserConfigError(f"Could not save Argus configuration at {config_path}.") from exc


def _secure_permissions(path: Path, *, directory: bool = False) -> None:
    try:
        os.chmod(path, 0o700 if directory else 0o600)
    except OSError:
        # Windows inherits the user's profile ACL for this directory and file.
        pass


def keyring_backend():
    try:
        import keyring

        backend = keyring.get_keyring()
        backend_name = type(backend).__name__.casefold()
        backend_module = type(backend).__module__.casefold()
        if (
            float(getattr(backend, "priority", 0)) <= 0
            or any(token in backend_name for token in ("fail", "null", "plaintext"))
            or "keyrings.alt.file" in backend_module
        ):
            return None
        return keyring
    except Exception:
        return None


def get_configured_gemini_key(config: dict[str, Any] | None = None) -> str | None:
    current = config if config is not None else load_user_config()
    llm = current.get("llm") or {}
    if not isinstance(llm, dict):
        return None
    key = llm.get("gemini_api_key")
    if isinstance(key, str) and key.strip():
        return key.strip()
    if llm.get("api_key_storage") == "keyring":
        backend = keyring_backend()
        if backend is not None:
            try:
                stored = backend.get_password(KEYRING_SERVICE, KEYRING_GEMINI_USERNAME)
                return stored.strip() if stored and stored.strip() else None
            except Exception:
                return None
    return None


def get_gemini_key_source(config: dict[str, Any] | None = None) -> str | None:
    if (os.environ.get("ARGUS_LLM_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip():
        return "environment"
    current = config if config is not None else load_user_config()
    llm = current.get("llm") or {}
    if isinstance(llm, dict):
        if isinstance(llm.get("gemini_api_key"), str) and llm["gemini_api_key"].strip():
            return "user config file"
        if llm.get("api_key_storage") == "keyring":
            backend = keyring_backend()
            if backend is not None:
                try:
                    if backend.get_password(KEYRING_SERVICE, KEYRING_GEMINI_USERNAME):
                        return "system keyring"
                except Exception:
                    pass
    return None


def store_gemini_key(config: dict[str, Any], api_key: str) -> str:
    """Store a new key in the system keyring or the private config file."""
    llm = config.setdefault("llm", {})
    if not isinstance(llm, dict):
        llm = {}
        config["llm"] = llm
    backend = keyring_backend()
    if backend is not None:
        try:
            backend.set_password(KEYRING_SERVICE, KEYRING_GEMINI_USERNAME, api_key)
            llm.pop("gemini_api_key", None)
            llm["api_key_storage"] = "keyring"
            return "system keyring"
        except Exception:
            pass
    llm["gemini_api_key"] = api_key
    llm["api_key_storage"] = "config file"
    return "user config file"
