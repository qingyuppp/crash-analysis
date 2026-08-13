#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runner="$root/run-vmcore-analysis"
test -x "$runner" || { echo 'run-vmcore-analysis must be executable' >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/cra-log"

cat > "$tmp/bin/cra" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
call_file="$CRA_LOG/calls"
call=1
if [[ -f "$call_file" ]]; then call=$(( $(<"$call_file") + 1 )); fi
printf '%s' "$call" > "$call_file"
printf '%s\n' "$@" > "$CRA_LOG/$call.args"
EOF
chmod +x "$tmp/bin/cra"

PATH="$tmp/bin:$PATH" CRA_LOG="$tmp/cra-log" "$runner" --no-jc > "$tmp/stdout" 2> "$tmp/stderr" || true

[[ -f "$tmp/cra-log/calls" ]] || { echo 'runner did not call cra' >&2; exit 1; }
test "$(<"$tmp/cra-log/calls")" = 2
diff -u - "$tmp/cra-log/1.args" <<'EOF'
vmcore
collect
--vmcore
/data/input/vmcore
--debuginfo
/data/input/debuginfo.rpm
--kernel
/data/input/kernel
--output-dir
/data/output
EOF
diff -u - "$tmp/cra-log/2.args" <<'EOF'
vmcore
classify
--collection
/data/output/collection.json
EOF
grep -Fq '==> collecting vmcore evidence' "$tmp/stdout"
grep -Fq '==> classifying vmcore evidence' "$tmp/stdout"
