#!/usr/bin/env bash
# Freestyle Jenkins job build script for koops analysis.
# Paste the body into: Job → Configure → Build Steps → Execute shell.
#
# Required parameters (Freestyle "This project is parameterized"):
#   String  VMCORE_URL      | VMCORE_PATH      — one of them; the other empty
#   String  DMESG_URL       | DMESG_PATH      — optional
#   String  DEBUG_RPM_URL   | DEBUG_RPM_PATH
#   String  KERNEL_SRC_URL  | KERNEL_SRC_PATH  — URL points to a tar/tar.gz/tar.xz archive
#   Choice  FOCUS           xfs | generic
#   Boolean RUN_JOYCODE     true = run JoyCode; false = evidence-only
#
# Required env (inject with Jenkins Credentials Binding when RUN_JOYCODE=true):
#   JOYCODE_API_KEY
#
# Node preconditions (one-time):
#   - jenkins user owns /work/pqy/kernel-oops (chown -R jenkins:jenkins ...)
#     so this script can curl/ln/rm/tar there without sudo.
#   - sudoers allows: jenkins NOPASSWD /usr/bin/docker, /usr/bin/chown
#
# All inputs are materialized under /work/pqy/kernel-oops/{crash,debug,kernel}
# (overwriting existing files each build), then bind-mounted into the container
# at the convention paths /data/input/*.

set -o pipefail
set -o errexit
set -o nounset

IMAGE_NAME='joycode-kernel-oops:latest'
STAGE_ROOT='/work/pqy/kernel-oops'
VMCORE_TARGET="$STAGE_ROOT/crash/vmcore"
DMESG_TARGET="$STAGE_ROOT/crash/vmcore-dmesg.txt"
DEBUG_RPM_TARGET="$STAGE_ROOT/debug/kernel-debuginfo.rpm"
KERNEL_TARGET="$STAGE_ROOT/kernel/vanguard"
OUTPUT_DIR="$WORKSPACE/output"

fix_output_ownership() {
    local status=$?
    if [ -d "$OUTPUT_DIR" ]; then
        sudo chown -R "$(id -u):$(id -g)" "$OUTPUT_DIR" || \
            echo "WARNING: unable to restore ownership of $OUTPUT_DIR" >&2
    fi
    return "$status"
}
trap fix_output_ownership EXIT

if [ "${RUN_JOYCODE:-true}" = "true" ] && [ -z "${JOYCODE_API_KEY:-}" ]; then
    echo "JOYCODE_API_KEY is required when RUN_JOYCODE=true; inject it with Jenkins Credentials Binding." >&2
    exit 2
fi

# Materialize one input: either curl it from URL, or ln -sf from a local PATH.
# Args: name, url, path, target
materialize_file() {
    local name="$1" url="$2" path="$3" target="$4"
    mkdir -p "$(dirname "$target")"
    if [ -n "$url" ]; then
        echo "==> $name: downloading $url"
        curl -fL --retry 3 --retry-delay 5 -o "$target" "$url"
    elif [ -n "$path" ]; then
        [ -r "$path" ] || { echo "$name: PATH not readable: $path" >&2; exit 2; }
        # Same path? nothing to do. Else replace target with a symlink to path.
        if [ "$(readlink -f "$path")" != "$(readlink -f "$target" 2>/dev/null || true)" ]; then
            echo "==> $name: linking $path -> $target"
            ln -sfn "$path" "$target"
        fi
    else
        echo "$name: neither URL nor PATH is set" >&2
        exit 2
    fi
}

# Materialize the kernel source tree (a directory, not a file).
materialize_kernel() {
    local url="$1" path="$2" target="$3"
    mkdir -p "$(dirname "$target")"
    if [ -n "$url" ]; then
        local archive="$STAGE_ROOT/kernel/kernel-source.download"
        echo "==> KERNEL_SRC: downloading $url"
        curl -fL --retry 3 --retry-delay 5 -o "$archive" "$url"
        rm -rf "$target"
        mkdir -p "$target"
        case "$url" in
            *.tar.gz|*.tgz)  tar -xzf "$archive" -C "$target" --strip-components=1 ;;
            *.tar.xz|*.txz)  tar -xJf "$archive" -C "$target" --strip-components=1 ;;
            *.tar)           tar -xf  "$archive" -C "$target" --strip-components=1 ;;
            *) echo "KERNEL_SRC_URL: unsupported archive extension: $url" >&2; exit 2 ;;
        esac
    elif [ -n "$path" ]; then
        [ -d "$path" ] || { echo "KERNEL_SRC: PATH is not a directory: $path" >&2; exit 2; }
        if [ "$(readlink -f "$path")" != "$(readlink -f "$target" 2>/dev/null || true)" ]; then
            echo "==> KERNEL_SRC: linking $path -> $target"
            rm -rf "$target"
            ln -sfn "$path" "$target"
        fi
    else
        echo "KERNEL_SRC: neither URL nor PATH is set" >&2
        exit 2
    fi
}

echo "===== Preflight ====="
whoami
id
sudo docker ps >/dev/null
sudo docker image inspect "$IMAGE_NAME" >/dev/null
mkdir -p "$OUTPUT_DIR"

echo "===== Materialize inputs ====="
materialize_file  VMCORE     "${VMCORE_URL:-}"     "${VMCORE_PATH:-}"     "$VMCORE_TARGET"
if [ -n "${DMESG_URL:-}" ] || [ -n "${DMESG_PATH:-}" ]; then
    materialize_file DMESG "${DMESG_URL:-}" "${DMESG_PATH:-}" "$DMESG_TARGET"
else
    rm -f "$DMESG_TARGET"
    echo "==> DMESG: not supplied; crash log will be used"
fi
materialize_file  DEBUG_RPM  "${DEBUG_RPM_URL:-}"  "${DEBUG_RPM_PATH:-}"  "$DEBUG_RPM_TARGET"
materialize_kernel "${KERNEL_SRC_URL:-}" "${KERNEL_SRC_PATH:-}" "$KERNEL_TARGET"

echo "===== Run analysis ====="
extra_args=""
[ "${RUN_JOYCODE:-true}" = "true" ] || extra_args="--no-jc"
dmesg_mount=""
[ ! -r "$DMESG_TARGET" ] || dmesg_mount="-v $DMESG_TARGET:/data/input/dmesg:ro"

sudo docker run --rm --network host \
    -e JOYCODE_API_KEY="${JOYCODE_API_KEY:-}" \
    -e JOYCODE_LOG=debug \
    -v "$VMCORE_TARGET:/data/input/vmcore:ro" \
    $dmesg_mount \
    -v "$DEBUG_RPM_TARGET:/data/input/debuginfo.rpm:ro" \
    -v "$KERNEL_TARGET:/data/input/kernel:ro" \
    -v "$OUTPUT_DIR:/data/output" \
    "$IMAGE_NAME" \
    run-vmcore-analysis $extra_args

echo "===== Fix ownership so Jenkins can archive ====="
fix_output_ownership
trap - EXIT

echo "===== Output ====="
ls -lh "$OUTPUT_DIR"
