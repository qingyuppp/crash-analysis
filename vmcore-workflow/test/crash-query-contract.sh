#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
query="$root/crash-query"
test -x "$query" || { echo 'crash-query must be executable' >&2; exit 1; }
grep -Fq 'queries.log' "$query"
grep -Fq 'crash -i' "$query"
grep -Fq -- '--command' "$query"
runner="$root/run-vmcore-analysis"
grep -Fq '$linux-kernel-oops Read' "$runner"
! grep -Fq '\$linux-kernel-oops Read' "$runner"
grep -Fq 'jc exec ' "$runner"
grep -Fq -- '--json' "$runner"
grep -Fq -- '--sandbox danger-full-access' "$runner"
grep -Fq -- '--skip-git-repo-check' "$runner"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"
evidence="$tmp/evidence.json"
commands="$tmp/commands.txt"
printf '%s\n' '{"inputs":{"vmlinux":"/fake/vmlinux","vmcore":"/fake/vmcore"}}' > "$evidence"
printf '%s\n' 'bt 224856' 'bt 284533' > "$commands"

cat > "$tmp/bin/crash" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >> "$CRASH_COUNT"
printf '%s\n' "$@" > "$CRASH_ARGS"
cat > "$CRASH_STDIN"
printf 'fake crash output\n'
EOF
chmod +x "$tmp/bin/crash"

CRASH_COUNT="$tmp/count" CRASH_ARGS="$tmp/args" CRASH_STDIN="$tmp/stdin" \
  PATH="$tmp/bin:$PATH" "$query" --evidence "$evidence" --commands-file "$commands" > "$tmp/result"
test "$(wc -l < "$tmp/count")" -eq 1
test "$(wc -l < "$tmp/stdin")" -eq 3
grep -Fxq 'bt 224856' "$tmp/stdin"
grep -Fxq 'bt 284533' "$tmp/stdin"
tail -n 1 "$tmp/stdin" | grep -Fxq 'exit'
grep -Fq 'fake crash output' "$tmp/queries.log"

if CRASH_COUNT="$tmp/count" CRASH_ARGS="$tmp/args" CRASH_STDIN="$tmp/stdin" \
  PATH="$tmp/bin:$PATH" "$query" --evidence "$evidence" --command sys --commands-file "$commands" > /dev/null 2> "$tmp/both.err"; then
  echo 'crash-query accepted both command sources' >&2
  exit 1
fi
grep -Fq 'mutually exclusive' "$tmp/both.err"

if CRASH_COUNT="$tmp/count" CRASH_ARGS="$tmp/args" CRASH_STDIN="$tmp/stdin" \
  PATH="$tmp/bin:$PATH" "$query" --evidence "$evidence" --commands-file "$tmp/missing.txt" > /dev/null 2> "$tmp/missing.err"; then
  echo 'crash-query accepted an unreadable commands file' >&2
  exit 1
fi
grep -Fq 'commands file is not readable or is empty' "$tmp/missing.err"

: > "$tmp/count"
CRASH_COUNT="$tmp/count" CRASH_ARGS="$tmp/args" CRASH_STDIN="$tmp/stdin" \
  PATH="$tmp/bin:$PATH" "$query" --evidence "$evidence" --command sys > "$tmp/single-result"
test "$(wc -l < "$tmp/count")" -eq 1
test "$(wc -l < "$tmp/stdin")" -eq 2
grep -Fxq 'sys' "$tmp/stdin"
tail -n 1 "$tmp/stdin" | grep -Fxq 'exit'
