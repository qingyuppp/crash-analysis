#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script="$root/jenkins-freestyle.sh"

require_line() {
    grep -Fq -- "$1" "$script" || {
        echo "missing expected Freestyle contract: $1" >&2
        exit 1
    }
}

require_line "IMAGE_NAME='joycode-kernel-oops:latest'"
require_line '[ "${RUN_JOYCODE:-true}" = "true" ] && [ -z "${JOYCODE_API_KEY:-}" ]'
require_line 'JOYCODE_API_KEY is required when RUN_JOYCODE=true'
require_line 'trap fix_output_ownership EXIT'
require_line 'run-vmcore-analysis'
! grep -Fq -- '--focus' "$script"
