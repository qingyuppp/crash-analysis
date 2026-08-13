#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dockerfile="$root/Dockerfile"
require() { grep -Fq -- "$1" "$dockerfile" || { echo "missing: $1" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$1" "$dockerfile" || { echo "forbidden: $1" >&2; exit 1; }; }
require 'COPY runtime/run-vmcore-analysis /usr/local/bin/run-vmcore-analysis'
require 'COPY skill/crash-analysis /opt/skills/crash-analysis'
require 'COPY skill/crash-analysis /root/.joycode/skills/crash-analysis'
require 'COPY cli /opt/crash-analysis/cli'
require 'python3 -m pip install --no-cache-dir /opt/crash-analysis/cli'
require 'cra --help'
require 'COPY runtime/joycode-entrypoint.sh /usr/local/bin/joycode-entrypoint'
forbid 'git clone --depth 1'
