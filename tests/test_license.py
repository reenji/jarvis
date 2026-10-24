import base64
import io
import json
import time
import urllib.error
import uuid

import pytest

from core.license import LicenseManager


pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


KID = "test-license-key"
API_KEY = "argus_" + "a" * 64


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def signing_material():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_key, b64url(public_key)


def make_token(private_key, *, exp=None, plan_exp=None, plan="monthly", daily_limit=120, signature_override=None):
    now = int(time.time())
    issued_at = int(exp) - 86400 if exp is not None else now - 5
    claims = {
        "iss": "argus-license",
        "aud": "argus-cli",
        "sub": str(uuid.uuid4()),
        "plan": plan,
        "entitlements": {"text_chat": True, "web_search": True, "voice": True, "screen_control": True},
        "limits": {"daily_usage": daily_limit, "web_search_daily": None, "screen_control_daily": None},
        "max_devices": 2,
        "plan_expires_at": plan_exp if plan_exp is not None else now + 30 * 86400,
        "config_pending": [],
        "reason": None,
        "iat": issued_at,
        "exp": exp if exp is not None else issued_at + 86400,
    }
    header = b64url(json.dumps({"alg": "EdDSA", "typ": "JWT", "kid": KID}, separators=(",", ":")).encode())
    payload = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = signature_override or private_key.sign(signing_input)
    return f"{header}.{payload}.{b64url(signature)}"


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def manager_for(tmp_path, monkeypatch, opener=None):
    private_key, public_key = signing_material()
    monkeypatch.setenv("ARGUS_LICENSE_API_URL", "https://license.example.test/functions/v1/license")
    monkeypatch.setenv("GEMINI_API_KEY", "provider-secret-must-stay-local")
    manager = LicenseManager(
        state_path=tmp_path / "license.json",
        public_keys={KID: public_key},
        opener=opener or (lambda *_args, **_kwargs: FakeResponse({"token": make_token(private_key)})),
    )
    monkeypatch.setattr(manager, "_keyring_get", lambda: None)
    monkeypatch.setattr(manager, "_keyring_set", lambda _value: False)
    monkeypatch.setattr(manager, "_keyring_delete", lambda: None)
    return manager, private_key


def test_login_sends_only_license_key_and_device_id(tmp_path, monkeypatch):
    captured = {}
    manager, private_key = manager_for(tmp_path, monkeypatch)

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["timeout"] = timeout
        return FakeResponse({"token": make_token(private_key), "reason": None})

    manager._opener = opener
    status = manager.login(API_KEY)

    assert status["state"] == "paid"
    assert set(captured["body"]) == {"device_id"}
    assert captured["headers"]["x-argus-key"] == API_KEY
    assert captured["headers"]["x-device-id"] == captured["body"]["device_id"]
    assert manager._read_state()["device_id"] == captured["body"]["device_id"]
    assert captured["timeout"] == 8
    wire_data = json.dumps(captured).lower()
    assert "provider-secret-must-stay-local" not in wire_data
    assert "prompt" not in captured["body"]


def test_cached_paid_token_allows_offline_grace_then_returns_to_free(tmp_path, monkeypatch):
    manager, private_key = manager_for(tmp_path, monkeypatch)
    now = int(time.time())
    token = make_token(private_key, exp=now - 10, plan_exp=now + 86400)
    manager._write_state({"token": token})
    assert manager.current_status()["state"] == "offline_grace"

    expired_token = make_token(
        private_key,
        exp=now - 3 * 86400 - 5,
        plan_exp=now + 86400,
    )
    manager._write_state({"token": expired_token})
    status = manager.current_status()
    assert status["state"] == "free"
    assert status["reason"] == "offline_grace_expired"


def test_expired_subscription_falls_back_to_free(tmp_path, monkeypatch):
    manager, private_key = manager_for(tmp_path, monkeypatch)
    now = int(time.time())
    token = make_token(private_key, exp=now - 10, plan_exp=now - 1)
    manager._write_state({"token": token})

    status = manager.current_status()
    assert status["state"] == "free"
    assert status["reason"] == "expired"
    assert status["entitlements"]["text_chat"] is True
    assert status["entitlements"]["voice"] is False


def test_revoked_key_drops_cached_paid_token_and_returns_to_free(tmp_path, monkeypatch):
    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "revoked",
            {},
            io.BytesIO(b'{"error":"revoked"}'),
        )

    manager, private_key = manager_for(tmp_path, monkeypatch, opener=opener)
    manager._write_state({"api_key": API_KEY, "token": make_token(private_key)})
    status = manager.refresh(force=True)

    assert status["state"] == "free"
    assert status["reason"] == "revoked"
    assert "token" not in manager._read_state()


def test_device_limit_returns_to_free_with_panel_instruction_reason(tmp_path, monkeypatch):
    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            409,
            "device_limit",
            {},
            io.BytesIO(b'{"error":"device_limit"}'),
        )

    manager, private_key = manager_for(tmp_path, monkeypatch, opener=opener)
    manager._write_state({"api_key": API_KEY, "token": make_token(private_key)})
    status = manager.refresh(force=True)

    assert status["state"] == "free"
    assert status["reason"] == "device_limit"


def test_login_reports_invalid_key_instead_of_claiming_success(tmp_path, monkeypatch):
    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "invalid_key",
            {},
            io.BytesIO(b'{"error":"invalid_key"}'),
        )

    manager, _private_key = manager_for(tmp_path, monkeypatch, opener=opener)
    from core.license import LicenseAPIError

    with pytest.raises(LicenseAPIError, match="invalid_key"):
        manager.login(API_KEY)
    assert manager.api_key() is None


def test_invalid_signature_is_rejected_and_uses_free(tmp_path, monkeypatch):
    manager, private_key = manager_for(tmp_path, monkeypatch)
    token = make_token(private_key, signature_override=b"x" * 64)
    manager._write_state({"token": token})

    status = manager.current_status()
    assert status["state"] == "free"
    assert status["reason"] == "invalid_token"


def test_local_daily_usage_limit_is_enforced(tmp_path, monkeypatch):
    manager, private_key = manager_for(tmp_path, monkeypatch)
    manager._write_state({"token": make_token(private_key)})

    allowed, configured_limit = manager.consume("daily_usage", 120)
    assert allowed is True
    assert configured_limit == 120
    allowed, configured_limit = manager.consume("daily_usage")
    assert allowed is False
    assert configured_limit == 120


def test_refresh_applies_changed_entitlements_from_server_matrix(tmp_path, monkeypatch):
    private_key, public_key = signing_material()
    replies = iter([
        {"token": make_token(private_key), "reason": None},
        {"token": make_token(private_key, plan="weekly", daily_limit=45), "reason": None},
    ])
    monkeypatch.setenv("ARGUS_LICENSE_API_URL", "https://license.example.test/functions/v1/license")
    manager = LicenseManager(
        state_path=tmp_path / "license.json",
        public_keys={KID: public_key},
        opener=lambda *_args, **_kwargs: FakeResponse(next(replies)),
    )
    monkeypatch.setattr(manager, "_keyring_get", lambda: None)
    monkeypatch.setattr(manager, "_keyring_set", lambda _value: False)
    monkeypatch.setattr(manager, "_keyring_delete", lambda: None)
    manager.login(API_KEY)
    assert manager.can("voice") is True

    manager.refresh(force=True)
    assert manager.current_status()["plan"] == "weekly"
    assert manager.limit("daily_usage") == 45


def test_refresh_checks_the_server_after_one_hour(tmp_path, monkeypatch):
    calls = 0
    manager, _private_key = manager_for(tmp_path, monkeypatch)
    original_opener = manager._opener

    def opener(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_opener(*args, **kwargs)

    manager._opener = opener
    manager.login(API_KEY)
    assert calls == 1
    manager.refresh(force=False)
    assert calls == 1

    state = manager._read_state()
    state["last_checked_at"] -= 3601
    manager._write_state(state)
    manager.refresh(force=False)
    assert calls == 2
