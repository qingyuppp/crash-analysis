#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runner="$root/analyze-vmcore"
require() { grep -Fq -- "$1" "$runner" || { echo "missing: $1" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$1" "$runner" || { echo "obsolete: $1" >&2; exit 1; }; }
require 'evidence.json'
require "outdir/focus"
require "'xfs.txt'"
require "'fault.txt'"
require "'hang.txt'"
require 'crash-raw.txt'
require 'queries.log'
forbid 'joycode-prompt.txt'
forbid 'xfs-buffer-summary.json'
forbid 'xfs-lock-graph.json'
forbid 'bt -f '
forbid 'JOYCODE_TIMEOUT'
