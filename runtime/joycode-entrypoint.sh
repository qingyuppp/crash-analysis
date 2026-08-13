#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${JOYCODE_API_KEY:-}" ]]; then
    echo "JOYCODE_API_KEY not set; skipping joycode config (evidence-only mode)" >&2
else
    mkdir -p /root/.joycode
    joycode_model="${JOYCODE_MODEL:-GLM-5.2}"
    context_window="${MODEL_CONTEXT_WINDOW:-1000000}"
    compact_limit="${MODEL_AUTO_COMPACT_TOKEN_LIMIT:-900000}"
    cat > /root/.joycode/config.toml <<EOF
active_channel = "custom"
model = "${joycode_model}"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_context_window = ${context_window}
model_max_output_tokens = 16384
model_auto_compact_token_limit = ${compact_limit}
multi_agent = false
worktree_enabled = true
max_concurrent_tasks = 1
hide_agent_reasoning = false

[[custom_models]]
id = "${joycode_model}"
label = "${joycode_model}"
description = "JoyBuilder model via OpenAI-compatible Chat API"
model = "${joycode_model}"
provider = "openai"
effort = "medium"

[model_providers.openai]
name = "openai"
base_url = "http://ai-api.jdcloud.com/v1"
api_key = "${JOYCODE_API_KEY}"
wire_api = "chat"

[projects."/work"]
trust_level = "trusted"
EOF
fi

exec "$@"
