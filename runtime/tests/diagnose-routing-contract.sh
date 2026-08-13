#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runner="$root/run-vmcore-analysis"
require() { grep -Fq -- "$1" "$runner" || { echo "missing: $1" >&2; exit 1; }; }
require 'cra vmcore diagnose compact-bt'
require 'cra vmcore diagnose task'
require 'cra vmcore diagnose query'
require 'cra vmcore diagnose structure'
require 'cra vmcore diagnose symbol'
require 'analysis_file=/data/output/analysis.md'
require 'JoyCode analysis did not complete'
