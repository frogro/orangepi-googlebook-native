#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="$(dirname "$ROOT")"
mkdir -p "$BASE/logs" "$BASE/tmp"
export TMPDIR="$BASE/tmp"
exec 9>"$BASE/logs/inspect.lock"
flock -n 9 || exit 1
python3 "$ROOT/tools/fetch-recovery.py" "$BASE/downloads"
python3 "$ROOT/tools/inspect-recovery.py" "$BASE/downloads/mica-recovery.raw" "$BASE/work/recovery-inspection"
