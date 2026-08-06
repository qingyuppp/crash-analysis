#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
pipeline="$root/Jenkinsfile"

require_line() {
    grep -Fq -- "$1" "$pipeline" || {
        echo "missing expected Jenkins container contract: $1" >&2
        exit 1
    }
}

forbid_line() {
    ! grep -Fq -- "$1" "$pipeline" || {
        echo "obsolete Jenkins container contract remains: $1" >&2
        exit 1
    }
}

require_line '-v "$INPUT_DIR/vmcore:/data/input/vmcore:ro"'
require_line 'if [ -r "$INPUT_DIR/vmcore-dmesg.txt" ]; then'
require_line 'dmesg_mount="-v $INPUT_DIR/vmcore-dmesg.txt:/data/input/dmesg:ro"'
require_line '-v "$DEBUG_DIR/kernel-debuginfo.rpm:/data/input/debuginfo.rpm:ro"'
require_line '-v "$KERNEL_DIR:/data/input/kernel:ro"'
require_line '-v "$OUTPUT_DIR:/data/output"'
forbid_line '--vmlinux'
require_line "stage('Build Analysis Image')"
require_line 'docker build --no-cache -f vmcore-workflow/joycode-kernel-oops-openeuler.Dockerfile'
require_line "booleanParam(name: 'RUN_JOYCODE'"
require_line 'run-vmcore-analysis'
forbid_line "choice(name: 'FOCUS'"
forbid_line '--focus'
