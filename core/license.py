"""Local Argus license client.

Only the Argus license key and a random device identifier are sent to the
license API. Provider credentials and conversation content stay in the app.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform
import secrets
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.license_keys import LICENSE_PUBLIC_KEYS

FREE_ENTITLEMENTS = {
    "text_chat": True,
    "web_search": True,
    "voice": False,
    "screen_control": False,
}
FREE_LIMITS = {
    "daily_usage": None,
    "web_search_daily": None,
    "screen_control_daily": None,
    "max_devices": 0,
}
PLAN_NAMES = {
    "free": "Grátis",
    "weekly": "Semanal",
    "monthly": "Mensal",
    "annual": "Anual",
}
TOKEN_LIFETIME_SECONDS = 24 * 60 * 60
OFFLINE_GRACE_SECONDS = 3 * 24 * 60 * 60
REFRESH_INTERVAL_SECONDS = 60 * 60
RENEW_URL = "https://argusdev.netlify.app/planos/"
LICENSE_API_URL = "https://iugvqlbyflrqlnninrlg.supabase.co/functions/v1/license"
KEYRING_SERVICE = "argus"
KEYRING_ACCOUNT = "license_api_key"


class LicenseError(RuntimeError):
    """A licensing operation could not be completed."""


class LicenseAPIError(LicenseError):
    def __init__(self, code: str, message: str = ""):
        self.code = str(code or "license_error")
        self.message = str(message or self.code)
        super().__init__(self.message)


def _b64url_decode(value: str) -> bytes:
    value = str(value or "").strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            return None
    return None


def _data_directory() -> Path:
    configured = os.environ.get("ARGUS_LICENSE_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Argus"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Argus"
    base = os.environ.get("XDG_DATA_HOME", "").strip()
    return (Path(base).expanduser() if base else Path.home() / ".local" / "share") / "argus"


def _secure_file(path: Path) -> None:
    """Restrict fallback state files to the current user where the OS permits."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    if os.name == "nt":
        username = os.environ.get("USERNAME", "").strip()
        domain = os.environ.get("USERDOMAIN", "").strip()
        if username:
            principal = f"{domain}\\{username}" if domain else username
            try:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{principal}:(F)"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except (OSError, subprocess.SubprocessError):
                pass


class LicenseManager:
    """Store the Argus key, verify cached tokens, and enforce local entitlements."""

    def __init__(
        self,
        *,
        state_path: str | Path | None = None,
        public_keys: dict[str, str] | None = None,
        opener=None,
    ):
        self.state_path = Path(state_path) if state_path else _data_directory() / "license.json"
        self.public_keys = dict(LICENSE_PUBLIC_KEYS if public_keys is None else public_keys)
        self._opener = opener or urllib.request.urlopen

    @property
    def api_base_url(self) -> str:
        return os.environ.get("ARGUS_LICENSE_API_URL", "").strip().rstrip("/") or LICENSE_API_URL

    @property
    def renew_url(self) -> str:
        return os.environ.get("ARGUS_LICENSE_RENEW_URL", RENEW_URL).strip() or RENEW_URL

    def _read_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        data = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(temp_path, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        _secure_file(temp_path)
        os.replace(temp_path, self.state_path)
        _secure_file(self.state_path)

    def _keyring_get(self) -> str | None:
        try:
            import keyring

            return keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception:
            return None

    def _keyring_set(self, value: str) -> bool:
        try:
            import keyring

            keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, value)
            return True
        except Exception:
            return False

    def _keyring_delete(self) -> None:
        try:
            import keyring

            keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception:
            pass

    def api_key(self) -> str | None:
        key = self._keyring_get()
        if key:
            return key
        value = self._read_state().get("api_key")
        return str(value).strip() if isinstance(value, str) and value.strip() else None

    def _save_api_key(self, key: str) -> None:
        state = self._read_state()
        if self._keyring_set(key):
            state.pop("api_key", None)
        else:
            state["api_key"] = key
        self._write_state(state)

    def _device_id(self) -> str:
        state = self._read_state()
        device_id = state.get("device_id")
        try:
            uuid.UUID(str(device_id))
        except (ValueError, TypeError, AttributeError):
            device_id = str(uuid.uuid4())
            state["device_id"] = device_id
            self._write_state(state)
        return str(device_id)

    def _request(self, operation: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        base = self.api_base_url
        if not base:
            raise LicenseAPIError(
                "configuration_missing",
                "Configure ARGUS_LICENSE_API_URL com a URL base das Edge Functions do Argus.",
            )
        request = urllib.request.Request(
            f"{base}/{operation}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Argus-Key": key,
                "X-Device-ID": self._device_id(),
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=8) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {}
            raise LicenseAPIError(
                body.get("error", "license_error"),
                body.get("message", body.get("error", "Erro no serviço de licenças.")),
            ) from exc
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            raise LicenseAPIError("network_error", "Não foi possível conectar ao serviço de licenças.") from exc
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LicenseAPIError("invalid_response", "O serviço de licenças retornou uma resposta inválida.") from exc
        if not isinstance(body, dict):
            raise LicenseAPIError("invalid_response", "O serviço de licenças retornou uma resposta inválida.")
        return body

    def _verify_token(self, token: str) -> dict[str, Any]:
        parts = str(token or "").split(".")
        if len(parts) != 3:
            raise LicenseAPIError("invalid_token", "Token de licença inválido.")
        try:
            header = json.loads(_b64url_decode(parts[0]))
            claims = json.loads(_b64url_decode(parts[1]))
            signature = _b64url_decode(parts[2])
        except (ValueError, json.JSONDecodeError) as exc:
            raise LicenseAPIError("invalid_token", "Token de licença inválido.") from exc
        if not isinstance(header, dict) or not isinstance(claims, dict) or header.get("alg") != "EdDSA":
            raise LicenseAPIError("invalid_token", "Token de licença inválido.")
        kid = str(header.get("kid") or "")
        encoded_key = self.public_keys.get(kid)
        if not encoded_key:
            raise LicenseAPIError("unknown_signing_key", "A chave pública do token não está neste build do Argus.")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            public_key = Ed25519PublicKey.from_public_bytes(_b64url_decode(encoded_key))
            public_key.verify(signature, f"{parts[0]}.{parts[1]}".encode("ascii"))
        except Exception as exc:
            raise LicenseAPIError("invalid_signature", "A assinatura do token de licença não é válida.") from exc
        if claims.get("aud") != "argus-cli" or claims.get("iss") != "argus-license":
            raise LicenseAPIError("invalid_token", "Token de licença emitido para outro serviço.")
        if claims.get("plan") not in PLAN_NAMES:
            raise LicenseAPIError("invalid_token", "O token contém um plano desconhecido.")
        exp = _timestamp(claims.get("exp"))
        if exp is None:
            raise LicenseAPIError("invalid_token", "O token não contém validade.")
        issued_at = _timestamp(claims.get("iat"))
        if issued_at is None or issued_at > time.time() + 60 or exp <= issued_at:
            raise LicenseAPIError("invalid_token", "O token contém datas inválidas.")
        if exp - issued_at > TOKEN_LIFETIME_SECONDS + 60:
            raise LicenseAPIError("invalid_token", "O token ultrapassa a duração máxima de 24 horas.")
        plan_exp = _timestamp(claims.get("plan_expires_at"))
        if plan_exp is not None and exp > plan_exp:
            raise LicenseAPIError("invalid_token", "O token ultrapassa a validade do plano.")
        return claims

    def login(self, key: str) -> dict[str, Any]:
        key = str(key or "").strip()
        if not key.startswith("argus_") or len(key) < 30:
            raise LicenseAPIError("invalid_key", "A chave deve começar com argus_ e conter o valor completo do painel.")
        if not self.api_base_url:
            raise LicenseAPIError(
                "configuration_missing",
                "Configure ARGUS_LICENSE_API_URL antes de conectar a chave.",
            )
        self._save_api_key(key)
        try:
            return self.refresh(force=True, raise_errors=True)
        except LicenseAPIError as exc:
            if exc.code in {"invalid_key", "revoked"}:
                self._keyring_delete()
                state = self._read_state()
                state.pop("api_key", None)
                state.pop("token", None)
                self._write_state(state)
            raise

    def refresh(self, *, force: bool = True, raise_errors: bool = False) -> dict[str, Any]:
        key = self.api_key()
        if not key or not self.api_base_url:
            return self.current_status()
        device_id = self._device_id()
        state = self._read_state()
        last_check = _timestamp(state.get("last_checked_at")) or 0
        if not force and time.time() - last_check < REFRESH_INTERVAL_SECONDS:
            return self.current_status()
        try:
            body = self._request("activate", key, {"device_id": device_id})
            token = body.get("token")
            if not isinstance(token, str) or not token:
                raise LicenseAPIError("invalid_response", "A resposta não contém um token de licença.")
            claims = self._verify_token(token)
            state.update({
                "token": token,
                "last_checked_at": time.time(),
                "server_reason": body.get("reason") or claims.get("reason"),
                "last_error": None,
            })
            self._write_state(state)
            return self.current_status()
        except LicenseAPIError as exc:
            state["last_checked_at"] = time.time()
            state["last_error"] = exc.code
            if exc.code in {"invalid_key", "revoked", "device_limit"}:
                state.pop("token", None)
                state["server_reason"] = exc.code
            elif exc.code in {"invalid_token", "invalid_signature", "unknown_signing_key"}:
                state.pop("token", None)
                state["server_reason"] = "invalid_token"
            self._write_state(state)
            if raise_errors:
                raise
            if exc.code in {
                "invalid_key", "revoked", "device_limit", "invalid_token",
                "invalid_signature", "unknown_signing_key",
            }:
                return self.current_status()
            return self.current_status()

    def deactivate(self) -> None:
        key = self.api_key()
        if key and self.api_base_url:
            self._request("deactivate", key, {"device_id": self._device_id()})

    def logout(self) -> None:
        try:
            self.deactivate()
        finally:
            self._keyring_delete()
            state = self._read_state()
            state.pop("api_key", None)
            state.pop("token", None)
            state.pop("last_checked_at", None)
            state.pop("server_reason", None)
            state.pop("last_error", None)
            self._write_state(state)

    def current_status(self) -> dict[str, Any]:
        state = self._read_state()
        token = state.get("token")
        if not isinstance(token, str) or not token:
            return self._free_status(state.get("server_reason"))
        try:
            claims = self._verify_token(token)
        except LicenseAPIError:
            return self._free_status("invalid_token")
        now = time.time()
        plan = str(claims.get("plan", "free"))
        exp = _timestamp(claims.get("exp")) or 0
        plan_exp = _timestamp(claims.get("plan_expires_at"))
        reason = state.get("server_reason") or claims.get("reason")
        if plan != "free" and plan_exp is not None and now >= plan_exp:
            return self._free_status("expired")
        if plan == "free":
            return self._free_status(reason)
        if now <= exp:
            return self._paid_status(claims, "paid")
        if now <= exp + OFFLINE_GRACE_SECONDS and (plan_exp is None or now < plan_exp):
            return self._paid_status(claims, "offline_grace")
        return self._free_status("offline_grace_expired")

    @staticmethod
    def _free_status(reason: Any = None) -> dict[str, Any]:
        return {
            "state": "free",
            "plan": "free",
            "reason": str(reason) if reason else None,
            "valid_until": None,
            "entitlements": dict(FREE_ENTITLEMENTS),
            "limits": dict(FREE_LIMITS),
            "max_devices": 0,
        }

    @staticmethod
    def _paid_status(claims: dict[str, Any], state: str) -> dict[str, Any]:
        entitlements = claims.get("entitlements")
        limits = claims.get("limits")
        return {
            "state": state,
            "plan": claims.get("plan", "free"),
            "reason": claims.get("reason"),
            "valid_until": claims.get("plan_expires_at"),
            "entitlements": entitlements if isinstance(entitlements, dict) else {},
            "limits": limits if isinstance(limits, dict) else {},
            "max_devices": claims.get("max_devices", 0),
        }

    def can(self, feature: str) -> bool:
        status = self.current_status()
        value = status["entitlements"].get(str(feature))
        return bool(value)

    def limit(self, name: str) -> int | None:
        status = self.current_status()
        value = status["limits"].get(str(name))
        if isinstance(value, bool) or not isinstance(value, int):
            fallback = FREE_LIMITS.get(str(name)) if status["state"] == "free" else None
            return fallback if isinstance(fallback, int) else None
        return max(0, value)

    def consume(self, name: str, amount: int = 1) -> tuple[bool, int | None]:
        """Count local usage and return whether it remains within the plan limit."""
        amount = max(1, int(amount))
        status = self.current_status()
        limit_value = self.limit(name)
        state = self._read_state()
        today = datetime.now(timezone.utc).date().isoformat()
        usage = state.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        counter = usage.get(today)
        counter = counter if isinstance(counter, dict) else {}
        used = max(0, int(counter.get(name, 0) or 0))
        next_used = used + amount
        counter[name] = next_used
        usage[today] = counter
        for date_key in list(usage):
            if date_key != today:
                usage.pop(date_key, None)
        state["usage"] = usage
        self._write_state(state)
        return limit_value is None or next_used <= limit_value, limit_value

    def banner(self) -> str:
        status = self.current_status()
        state = status["state"]
        reason = status.get("reason")
        renew = self.renew_url
        if state in {"paid", "offline_grace"}:
            plan_name = PLAN_NAMES.get(status["plan"], status["plan"])
            expiry = _timestamp(status.get("valid_until"))
            expiry_text = (
                datetime.fromtimestamp(expiry).astimezone().strftime("%d/%m/%Y %H:%M")
                if expiry is not None else "sem validade informada"
            )
            if state == "offline_grace":
                return f"Carência offline ativa — plano {plan_name}, válido até {expiry_text}."
            if expiry is not None and expiry - time.time() <= 3 * 24 * 60 * 60:
                return f"Plano {plan_name} válido até {expiry_text}. Renove: {renew}"
            return f"Plano {plan_name} ativo até {expiry_text}."
        if reason == "expired":
            return f"Plano expirado. O Argus continua no grátis. Renove: {renew}"
        if reason == "revoked":
            return f"Chave Argus revogada. O Argus continua no grátis. Gere outra chave no painel: {renew}"
        if reason == "device_limit":
            return f"Limite de dispositivos atingido. Remova um dispositivo no painel: {renew}"
        if reason == "offline_grace_expired":
            return f"Carência offline encerrada. O Argus continua no grátis. Conecte à internet ou renove: {renew}"
        return f"Plano grátis. Voz e controle de tela não estão disponíveis. Planos: {renew}"


def handle_license_cli(args: list[str]) -> int | None:
    """Run a license command; return None when the app should start normally."""
    if not args or args[0] not in {"login", "status", "logout", "license"}:
        return None
    command = args[0]
    manager = LicenseManager()
    if command == "license":
        print("Uso: argus login | argus status | argus logout")
        return 0
    if command == "login":
        try:
            key = getpass.getpass("Cole a chave Argus (entrada oculta): ").strip()
            status = manager.login(key)
        except LicenseAPIError as exc:
            print(f"Não foi possível conectar a licença ({exc.code}): {exc.message}")
            if exc.code == "device_limit":
                print(f"Remova um dispositivo no painel: {manager.renew_url}")
            return 1
        print("Licença conectada.")
        print(manager.banner())
        if status.get("state") == "free" and status.get("reason") == "expired":
            print("A chave está válida; a assinatura expirou e o Argus seguirá no plano grátis.")
        return 0
    if command == "status":
        manager.refresh(force=True)
        print(manager.banner())
        return 0
    try:
        manager.logout()
        print("Chave removida deste dispositivo.")
        return 0
    except LicenseAPIError as exc:
        print(f"Não foi possível confirmar a desativação no servidor ({exc.code}). A chave local foi removida.")
        return 0

