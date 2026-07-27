#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
skill="$root/linux-kernel-oops/SKILL.md"
flows="$root/linux-kernel-oops/references/flows.md"
evidence="$root/linux-kernel-oops/references/vmcore-evidence.md"
agent="$root/linux-kernel-oops/agents/vmcore-evidence.agent.md"

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
require_text "$skill" "Do not give raw vmcore directly to an LLM"
require_text "$flows" "Vmcore Evidence Acquisition"
require_text "$flows" "XFS hang / filesystem deadlock"
require_text "$evidence" "crash-focused.txt"
require_text "$evidence" "matching vmlinux"
require_text "$agent" "do not analyse"
