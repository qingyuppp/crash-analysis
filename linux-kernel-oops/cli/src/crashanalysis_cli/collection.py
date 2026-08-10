"""Deterministic first-pass crash collection."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence


FIRST_PASS_COMMANDS = (
    "set scroll off",
    "sys",
    "log",
    "ps -m",
    "bt -a",
    "foreach UN bt",
    "mod",
    "mount",
    "kmem -i",
    "exit",
)


class CollectionError(RuntimeError):
    """A required input or external collection command was unsuccessful."""


@dataclass(frozen=True)
class CollectionInputs:
    vmcore: Path
    debuginfo: Path
    kernel: Path
    output_dir: Path
    dmesg: Optional[Path] = None


CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]


def _run(args: Sequence[str], *, cwd: Optional[Path] = None,
         input_bytes: Optional[bytes] = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 -- command arguments are fixed paths
        list(args), cwd=cwd, input=input_bytes, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )


def _require_readable(path: Path, label: str) -> None:
    if not path.is_file() or not path.stat().st_size >= 0:
        raise CollectionError(f"{label} is not a readable file: {path}")


def _checked(result: subprocess.CompletedProcess[bytes], label: str) -> bytes:
    if result.returncode:
        stderr = result.stderr.decode(errors="replace").strip()
        detail = f": {stderr}" if stderr else ""
        raise CollectionError(f"{label} failed with exit status {result.returncode}{detail}")
    return result.stdout


def collect_vmcore(inputs: CollectionInputs, *, run: CommandRunner = _run) -> dict:
    """Collect fixed crash output and return the persisted handoff document."""
    _require_readable(inputs.vmcore, "vmcore")
    _require_readable(inputs.debuginfo, "debuginfo")
    if not inputs.kernel.is_dir():
        raise CollectionError(f"kernel source directory does not exist: {inputs.kernel}")
    if inputs.dmesg is not None:
        _require_readable(inputs.dmesg, "dmesg")

    output_dir = inputs.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = output_dir / "debug"
    debug_dir.mkdir(exist_ok=True)
    rpm = _checked(run(["rpm2cpio", str(inputs.debuginfo)]), "rpm2cpio")
    _checked(run(["cpio", "-idmu", "--quiet"], cwd=debug_dir, input_bytes=rpm), "cpio")

    candidates = sorted(debug_dir.glob("usr/lib/debug/lib/modules/**/vmlinux"))
    if not candidates:
        raise CollectionError(f"vmlinux not found after unpacking {inputs.debuginfo}")
    vmlinux = candidates[0]

    command_file = output_dir / "crash.cmds"
    command_file.write_text("\n".join(FIRST_PASS_COMMANDS) + "\n")
    crash = _checked(
        run(["crash", "-i", str(command_file), str(vmlinux), str(inputs.vmcore)]),
        "crash",
    )
    raw = output_dir / "crash-raw.txt"
    raw.write_bytes(crash)
    collection = {
        "schema_version": 1,
        "inputs": {
            "vmcore": str(inputs.vmcore),
            "debuginfo": str(inputs.debuginfo),
            "kernel": str(inputs.kernel),
            "dmesg": str(inputs.dmesg) if inputs.dmesg else None,
        },
        "output_dir": str(output_dir),
        "vmlinux": str(vmlinux),
        "crash_commands": str(command_file),
        "crash_raw": str(raw),
    }
    (output_dir / "collection.json").write_text(
        json.dumps(collection, indent=2, sort_keys=True) + "\n"
    )
    return collection
