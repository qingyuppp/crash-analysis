#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
script="$root/jenkins-workflow.sh"

require_line() {
    grep -Fq -- "$1" "$script" || {
        echo "missing expected Freestyle contract: $1" >&2
        exit 1
    }
}

require_line "IMAGE_NAME='crash-analysis:latest'"
require_line 'JENKINS_WORKSPACE="${WORKSPACE:-$(pwd)}"'
require_line 'REPO_ROOT="${REPO_ROOT:-/work/pqy/crash-analysis}"'
require_line 'STAGE_ROOT="${STAGE_ROOT:-/work/pqy/crash-analysis-runtime}"'
require_line '[ "${RUN_JOYCODE:-true}" = "true" ] && [ -z "${JOYCODE_API_KEY:-}" ]'
require_line 'JOYCODE_API_KEY is required when RUN_JOYCODE=true'
require_line 'trap fix_output_ownership EXIT'
require_line 'run-vmcore-analysis'
require_line 'JOYCODE_MODEL="${JOYCODE_MODEL:-GLM-5.2}"'
require_line 'MODEL_CONTEXT_WINDOW="${MODEL_CONTEXT_WINDOW:-1000000}"'
require_line 'MODEL_AUTO_COMPACT_TOKEN_LIMIT="${MODEL_AUTO_COMPACT_TOKEN_LIMIT:-900000}"'
require_line 'BUILD_IMAGE="${BUILD_IMAGE:-false}"'
require_line 'if [ "$BUILD_IMAGE" = "true" ]'
require_line 'sudo chown -R "$(id -u):$(id -g)" "$OUTPUT_DIR"'
! grep -Fq -- '--focus' "$script"
