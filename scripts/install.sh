#!/usr/bin/env bash
# Install the ARGUS CLI from GitHub on macOS or Linux, then run first-time setup.
set -euo pipefail

readonly REPOSITORY_URL="git+https://github.com/reenji/jarvis.git"
readonly DISTRIBUTION_NAME="argus-mark-xxxix"
INSTALL_VOICE=false

usage() {
  cat <<'EOF'
Usage: scripts/install.sh [--voice]

Install ARGUS from GitHub with uv or pipx, then run `argus setup`.
Pass --voice to include the optional microphone and speaker dependencies.
EOF
}

while (($#)); do
  case "$1" in
    --voice) INSTALL_VOICE=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "ARGUS requires Python 3.11 or newer. Install Python, then run this script again." >&2
  exit 1
fi

EXTRAS=""
if [[ "$INSTALL_VOICE" == true ]]; then
  EXTRAS="[voice]"
fi
PACKAGE_SPEC="${DISTRIBUTION_NAME}${EXTRAS} @ ${REPOSITORY_URL}"

if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
  "$UV_BIN" tool install --python "$PYTHON_BIN" "$PACKAGE_SPEC"
  ARGUS_BIN_DIR="$("$UV_BIN" tool dir --bin)"
elif command -v pipx >/dev/null 2>&1; then
  PIPX_BIN="$(command -v pipx)"
  "$PIPX_BIN" install --force --python "$PYTHON_BIN" "$PACKAGE_SPEC"
  ARGUS_BIN_DIR="$("$PIPX_BIN" environment --value PIPX_BIN_DIR)"
else
  cat >&2 <<'EOF'
Install uv or pipx first, then run this script again:
  https://docs.astral.sh/uv/getting-started/installation/
  https://pipx.pypa.io/stable/installation/
EOF
  exit 1
fi

ARGUS_COMMAND="${ARGUS_BIN_DIR%/}/argus"
if [[ ! -x "$ARGUS_COMMAND" ]]; then
  ARGUS_COMMAND="$(command -v argus || true)"
fi
if [[ -z "$ARGUS_COMMAND" || ! -x "$ARGUS_COMMAND" ]]; then
  echo "ARGUS was installed, but its command was not found. Add the installer bin directory to PATH, then run `argus setup`." >&2
  exit 1
fi

"$ARGUS_COMMAND" setup
