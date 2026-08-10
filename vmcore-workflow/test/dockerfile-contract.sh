#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dockerfile="$root/joycode-kernel-oops-openeuler.Dockerfile"
require() { grep -Fq -- "$1" "$dockerfile" || { echo "missing: $1" >&2; exit 1; }; }
forbid() { ! grep -Fq -- "$1" "$dockerfile" || { echo "forbidden: $1" >&2; exit 1; }; }
require 'COPY analyze-vmcore /usr/local/bin/analyze-vmcore'
require 'COPY crash-query /usr/local/bin/crash-query'
require 'COPY run-vmcore-analysis /usr/local/bin/run-vmcore-analysis'
require 'COPY lib/classify_evidence.py /usr/local/lib/kernel-analysis/classify_evidence.py'
require 'git clone --depth 1 --branch main https://github.com/qingyuppp/linux-kernel-analysis.git /tmp/linux-kernel-analysis'
require 'cp -a /tmp/linux-kernel-analysis/linux-kernel-oops /opt/skills/linux-kernel-oops'
require 'python3 -m pip install --no-cache-dir /opt/skills/linux-kernel-oops/cli'
require 'cra --help'
require 'COPY joycode-entrypoint.sh /usr/local/bin/joycode-entrypoint'
forbid 'COPY linux-kernel-oops /opt/skills/linux-kernel-oops'
