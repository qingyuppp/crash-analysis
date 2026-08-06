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
cat <<'BT'
PID: 224856 TASK: ffff000000000001 CPU: 1 COMMAND: "kworker/u"
 #0 [ffff000000001000] __schedule at ffffffff00001000
 #1 [ffff000000001100] xfs_buf_lock at ffffffffc0001000 [xfs]
 #2 [ffff000000001200] xfs_imap_to_bp at ffffffffc0002000 [xfs]
 #3 [ffff000000001300] xfs_vm_writepages at ffffffffc0003000 [xfs]

PID: 284533 TASK: ffff000000000002 CPU: 2 COMMAND: "kworker/2:1"
 #0 [ffff000000002000] __schedule at ffffffff00001000
 #1 [ffff000000002100] xfs_buf_lock at ffffffffc0001000 [xfs]
 #2 [ffff000000002200] xfs_read_agf at ffffffffc0002000 [xfs]
 #3 [ffff000000002300] xfs_ifree at ffffffffc0003000 [xfs]
 #4 [ffff000000002400] xfs_inodegc_worker at ffffffffc0004000 [xfs]

PID: 284539 TASK: ffff000000000003 CPU: 3 COMMAND: "kworker/3:1"
 #0 [ffff000000003000] __schedule at ffffffff00001000
 #1 [ffff000000003100] xfs_buf_lock at ffffffffc0001000 [xfs]
 #2 [ffff000000003200] xfs_read_agf at ffffffffc0002000 [xfs]
 #3 [ffff000000003300] xfs_ifree at ffffffffc0003000 [xfs]
 #4 [ffff000000003400] xfs_inodegc_worker at ffffffffc0004000 [xfs]
BT
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

compact_commands="$tmp/compact-commands.txt"
printf '%s\n' 'bt 224856' 'bt 284533' 'bt 284539' > "$compact_commands"
: > "$tmp/count"
rm -f "$tmp/queries.log"
CRASH_COUNT="$tmp/count" CRASH_ARGS="$tmp/args" CRASH_STDIN="$tmp/stdin" \
  PATH="$tmp/bin:$PATH" "$query" --evidence "$evidence" --commands-file "$compact_commands" --compact-bt > "$tmp/compact-result"
test "$(wc -l < "$tmp/count")" -eq 1
grep -Fq 'direct_xfs_buf_lock_waiters: 3' "$tmp/queries.log"
grep -Fq 'kind: inode_cluster' "$tmp/queries.log"
grep -Fq 'pids: 224856' "$tmp/queries.log"
grep -Fq 'kind: agf' "$tmp/queries.log"
grep -Fq 'pids: 284533, 284539' "$tmp/queries.log"
grep -Fq 'xfs_buf_lock > xfs_read_agf > xfs_ifree > xfs_inodegc_worker' "$tmp/queries.log"
! grep -Fq 'ffff000000002100' "$tmp/queries.log"
! grep -Fq 'fake crash output' "$tmp/queries.log"

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
