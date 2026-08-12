"""Crash-query compatible diagnostic actions and per-action artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


class DiagnosisError(RuntimeError):
    """Invalid evidence or failed crash diagnostic."""


CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]


def _run(args: Sequence[str], *, cwd: Optional[Path] = None,
         input_bytes: Optional[bytes] = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(list(args), cwd=cwd, input=input_bytes,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _load(evidence_path: Path) -> tuple[dict[str, Any], Path, Path, Path]:
    try:
        evidence = json.loads(evidence_path.read_text())
        inputs = evidence["inputs"]
        vmlinux, vmcore = Path(inputs["vmlinux"]), Path(inputs["vmcore"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise DiagnosisError(f"invalid evidence file: {evidence_path}") from error
    if not vmlinux.is_file() or not vmcore.is_file():
        raise DiagnosisError(f"vmlinux or vmcore is not readable: {vmlinux}, {vmcore}")
    return evidence, evidence_path.parent, vmlinux, vmcore


def _next_action_dir(output_dir: Path, action: str) -> Path:
    root = output_dir / "actions"
    root.mkdir(parents=True, exist_ok=True)
    numbers = [int(path.name.split("-", 1)[0]) for path in root.iterdir()
               if path.is_dir() and path.name.split("-", 1)[0].isdigit()]
    number = max(numbers, default=0) + 1
    path = root / f"{number:03d}-{action}"
    path.mkdir()
    return path


def _execute(evidence_path: Path, action: str, commands: list[str], request: dict[str, Any],
             *, run: CommandRunner = _run) -> dict[str, Any]:
    _evidence, output_dir, vmlinux, vmcore = _load(evidence_path)
    action_dir = _next_action_dir(output_dir, action)
    command_text = "\n".join(commands) + "\nexit\n"
    (action_dir / "request.json").write_text(json.dumps({"schema_version": 1, "action": action, **request}, indent=2, sort_keys=True) + "\n")
    (action_dir / "commands.txt").write_text(command_text)
    completed = run(["crash", "-i", str(action_dir / "commands.txt"), str(vmlinux), str(vmcore)])
    raw = completed.stdout + completed.stderr
    (action_dir / "raw.txt").write_bytes(raw)
    status = "ok" if completed.returncode == 0 else "failed"
    result = {"schema_version": 1, "action": action, "status": status,
              "request": request, "commands": commands,
              "raw_artifact": str(action_dir / "raw.txt"), "queries_log": str(output_dir / "queries.log")}
    (action_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with (output_dir / "queries.log").open("a") as log:
        log.write(f"\n## {action}\n\n```text\n{command_text}```\n\n```text\n")
        log.write(raw.decode(errors="replace"))
        log.write("\n```\n")
    if completed.returncode != 0:
        raise DiagnosisError(f"crash failed with exit status {completed.returncode}: {action_dir / 'raw.txt'}")
    return result


def diagnose_query(evidence_path: Path, command: str, *, run: CommandRunner = _run) -> dict[str, Any]:
    if not command.strip():
        raise DiagnosisError("command must not be empty")
    return _execute(evidence_path, "query", [command], {"command": command}, run=run)


def diagnose_compact_bt(evidence_path: Path, pids: list[int], *, run: CommandRunner = _run) -> dict[str, Any]:
    if not pids:
        raise DiagnosisError("at least one PID is required")
    return _execute(evidence_path, "compact-bt", [f"bt {pid}" for pid in pids], {"pids": pids}, run=run)


def diagnose_task(evidence_path: Path, pid: int, *, run: CommandRunner = _run) -> dict[str, Any]:
    return _execute(evidence_path, "task", [f"bt -f {pid}"], {"pid": pid}, run=run)


def diagnose_structure(evidence_path: Path, structure_type: str, address: str, *, run: CommandRunner = _run) -> dict[str, Any]:
    if not structure_type or not address:
        raise DiagnosisError("structure type and address are required")
    return _execute(evidence_path, "structure", [f"struct {structure_type} {address}"],
                    {"type": structure_type, "address": address}, run=run)


def diagnose_symbol(evidence_path: Path, name: str, *, run: CommandRunner = _run) -> dict[str, Any]:
    if not name:
        raise DiagnosisError("symbol name is required")
    return _execute(evidence_path, "symbol", [f"p {name}"], {"name": name}, run=run)
