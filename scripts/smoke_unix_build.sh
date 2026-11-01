#!/usr/bin/env bash
# Smoke test a packaged macOS or Linux ARGUS executable without an API key.
#
# Usage: scripts/smoke_unix_build.sh <path-to-ARGUS-executable>
#
# Checks --version, that `doctor` reports the missing key (exit 1, no Gemini
# request), that the desktop window starts (Qt offscreen, clap gate skipped),
# and that nothing was written inside the app's own folder.
set -euo pipefail

argus=${1:?usage: smoke_unix_build.sh <ARGUS executable>}
app_dir=$(cd "$(dirname "$argus")" && pwd)
case "$app_dir" in *.app/Contents/MacOS) app_dir=$(dirname "$(dirname "$app_dir")") ;; esac
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

unset GEMINI_API_KEY ARGUS_LLM_GEMINI_API_KEY ARGUS_DATA_DIR || true
export ARGUS_HOME="$scratch/argus-home" HOME="$scratch/home"
mkdir -p "$HOME"
before=$(find "$app_dir" -newer "$argus" -print | wc -l)

"$argus" --version

set +e
doctor=$("$argus" doctor 2>&1)
status=$?
set -e
echo "$doctor"
[ "$status" -eq 1 ] || { echo "argus doctor exited $status, expected 1" >&2; exit 1; }
grep -q "No usable API key found" <<<"$doctor" || { echo "doctor did not report the missing key" >&2; exit 1; }

# Desktop window: a pty keeps the frozen app's output line-buffered.
log="$scratch/desktop.log"
desktop=("$argus" desktop)
if [ "$(uname)" = Darwin ]; then
  QT_QPA_PLATFORM=offscreen ARGUS_SKIP_CLAP_GATE=1 script -q "$log" "${desktop[@]}" >/dev/null 2>&1 &
else
  QT_QPA_PLATFORM=offscreen ARGUS_SKIP_CLAP_GATE=1 script -qfec "${desktop[*]}" "$log" >/dev/null 2>&1 &
fi
pid=$!
ready=no
for _ in $(seq 1 90); do
  if grep -q "Interface ready" "$log" 2>/dev/null; then ready=yes; break; fi
  kill -0 "$pid" 2>/dev/null || break
  sleep 1
done
kill "$pid" 2>/dev/null || true
pkill -f "$argus desktop" 2>/dev/null || true
cat "$log" || true
[ "$ready" = yes ] || { echo "desktop window did not reach 'Interface ready'" >&2; exit 1; }

after=$(find "$app_dir" -newer "$argus" -print | wc -l)
[ "$after" -eq "$before" ] || { echo "the app wrote inside $app_dir:" >&2; find "$app_dir" -newer "$argus" -print >&2; exit 1; }
echo "Smoke test passed for $argus"
