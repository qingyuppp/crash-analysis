#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
query="$root/crash-query"
test -x "$query" || { echo 'crash-query must be executable' >&2; exit 1; }
grep -Fq 'queries.log' "$query"
grep -Fq 'crash -i' "$query"
grep -Fq -- '--command' "$query"
