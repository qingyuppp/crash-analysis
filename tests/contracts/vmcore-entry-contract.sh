#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
skill="$root/skill/crash-analysis/SKILL.md"
flows="$root/skill/crash-analysis/references/flows.md"
evidence="$root/skill/crash-analysis/references/vmcore-evidence.md"
agent="$root/skill/crash-analysis/agents/vmcore-evidence.agent.md"

require_file() {
    test -f "$1" || { echo "missing required file: $1" >&2; exit 1; }
}

require_text() {
    grep -Fq -- "$2" "$1" || {
        echo "missing required text in $1: $2" >&2
        exit 1
    }
}

require_file "$evidence"
require_file "$agent"
require_text "$skill" "vmcore"
require_text "$skill" "Do not read raw vmcore"
require_text "$flows" "Vmcore input routing"
require_text "$flows" "XFS hang / filesystem deadlock"
require_text "$evidence" "focus/xfs.txt"
require_text "$evidence" "matching vmlinux"
require_text "$agent" "do not analyse"
