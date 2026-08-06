#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${JOYCODE_API_KEY:-}" ]]; then
    echo "JOYCODE_API_KEY not set; skipping joycode config (evidence-only mode)" >&2
else
    mkdir -p /root/.joycode
    cat > /root/.joycode/config.toml <<EOF
active_channel = "custom"
model = "JoyAI-Code"
approval_policy = "never"
sandbox_mode = "danger-full-access"
model_context_window = 200000
model_max_output_tokens = 16384
multi_agent = true
worktree_enabled = true
max_concurrent_tasks = 3
hide_agent_reasoning = false

[[custom_models]]
id = "JoyAI-Code"
label = "JoyAI-Code"
description = "ChatRhino JoyAI-Code via OpenAI-compatible Function Call API"
model = "JoyAI-Code"
provider = "openai"
effort = "medium"

[model_providers.openai]
name = "openai"
base_url = "http://api.chatrhino.jd.com/api/v1"
api_key = "${JOYCODE_API_KEY}"
wire_api = "chat"

[projects."/work"]
trust_level = "trusted"
EOF
fi

exec "$@"
