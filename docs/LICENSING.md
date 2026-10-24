# Argus licensing client

The CLI license client is in `core/license.py`. It defaults to the deployed Argus endpoint at `https://iugvqlbyflrqlnninrlg.supabase.co/functions/v1/license`. Set `ARGUS_LICENSE_API_URL` only when using another deployment. The optional `ARGUS_LICENSE_RENEW_URL` controls links shown in status banners.

## Operator setup

- Keep the Ed25519 private signing key only in Supabase Edge Function secrets.
- Add the corresponding public key and `kid` to `core/license_keys.py` before building the CLI that will verify its tokens.
- Generate a key pair locally with `python scripts/generate_license_signing_key.py`; do not commit or share its private output.
- Follow `Site_argus/docs/licensing-v1.md` for migration, Edge Function, plan-matrix and manual-grant setup.

## User commands

- `argus login` asks for the one-time key from the account panel with hidden input.
- `argus status` forces a refresh and prints the current plan, expiration, and any recovery action.
- `argus logout` deactivates the current device when online and removes the local license key and token.
- `/status` in the Argus conversation displays the status and applies newly refreshed voice access.

The API receives only the Argus license key and the random `device_id`. Provider API keys, prompts, and conversation contents remain local to the application. Tokens are Ed25519 signed, have a maximum 24-hour lifetime, and cannot exceed the plan's validity. The CLI checks for updates hourly during a live session, allows a three-day grace period after token expiration while the paid plan itself remains valid, and falls back to free entitlements after that grace period.

The Supabase schema and both Edge Functions are deployed. Numeric usage caps, prices, and manual payment instructions remain pending. Until the signing-key pair is configured and the public key is embedded in a CLI release, paid-license activation is not ready. Free use works without login or a license server.
