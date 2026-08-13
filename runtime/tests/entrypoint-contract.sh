#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
entrypoint="$root/joycode-entrypoint.sh"
runner="$root/run-vmcore-analysis"

grep -Fq 'joycode_model="${JOYCODE_MODEL:-GLM-5.2}"' "$entrypoint"
grep -Fq 'id = "${joycode_model}"' "$entrypoint"
grep -Fq 'api_key = "${JOYCODE_API_KEY}"' "$entrypoint"
grep -Fq 'base_url = "http://ai-api.jdcloud.com/v1"' "$entrypoint"
grep -Fq 'context_window="${MODEL_CONTEXT_WINDOW:-1000000}"' "$entrypoint"
grep -Fq 'compact_limit="${MODEL_AUTO_COMPACT_TOKEN_LIMIT:-900000}"' "$entrypoint"
grep -Fq -- '--channel custom --model "${JOYCODE_MODEL:-GLM-5.2}"' "$runner"
grep -Fq -- 'Use $crash-analysis' "$runner"
