"""Create a one-time Ed25519 signing key pair for the Supabase license API.

Run this locally and copy the private value directly into a Supabase Edge
Function secret. Never commit or share the private value.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def main() -> None:
    private_key = Ed25519PrivateKey.generate()
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    print("LICENSE_SIGNING_KID=argus-2026-01")
    print(f"LICENSE_SIGNING_PRIVATE_KEY={_b64url(private_der)}")
    print(f"PUBLIC_KEY_FOR_CORE_LICENSE_KEYS={_b64url(public_raw)}")
    print("Store LICENSE_SIGNING_PRIVATE_KEY only as a Supabase Edge Function secret.")
    print("Add the public value to core/license_keys.py before building the CLI.")


if __name__ == "__main__":
    main()
