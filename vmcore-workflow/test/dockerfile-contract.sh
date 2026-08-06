#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dockerfile="$root/joycode-kernel-oops-openeuler.Dockerfile"
require() { grep -Fq -- "$1" "$dockerfile" || { echo "missing: $1" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$1" "$dockerfile" || { echo "forbidden: $1" >&2; exit 1; }; }
require 'COPY vmcore-workflow/analyze-vmcore /usr/local/bin/analyze-vmcore'
require 'COPY vmcore-workflow/crash-query /usr/local/bin/crash-query'
require 'COPY vmcore-workflow/run-vmcore-analysis /usr/local/bin/run-vmcore-analysis'
require 'COPY vmcore-workflow/lib/classify_evidence.py /usr/local/lib/kernel-analysis/classify_evidence.py'
require 'COPY linux-kernel-oops /opt/skills/linux-kernel-oops'
require 'COPY joycode-entrypoint.sh /usr/local/bin/joycode-entrypoint'
forbid 'git clone --depth 1'
