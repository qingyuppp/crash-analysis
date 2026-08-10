"""Convert fixed first-pass crash text into bounded routing evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


TASK_HEADER = re.compile(r'^PID:\s*(?P<pid>\d+)\s+TASK:\s*(?P<task>\S+).*?COMMAND:\s*"(?P<comm>[^"]+)"')
FRAME = re.compile(r'^\s*#\d+\s+\[[^]]+\]\s+(?P<name>[^\s+]+)')
SYSRQ_CRASH = re.compile(r'^.*Kernel panic - not syncing: sysrq triggered crash.*(?:\n|$)', re.IGNORECASE | re.MULTILINE)
FAULT_SIGNATURE = re.compile(r'\b(?:Kernel panic\b|Oops:|BUG:|WARNING:)', re.IGNORECASE)
BLOCKING_SITES = (
    "xfs_buf_lock", "xlog_grant_head_wait", "blk_mq_get_tag", "submit_bio",
    "io_schedule", "rwsem_down_write_slowpath", "rwsem_down_read_slowpath",
    "mutex_lock", "wait_for_completion",
)


class ClassificationError(RuntimeError):
    """The collection handoff is invalid or inaccessible."""


def subsystem_for(frames: list[str], blocking_site: str) -> str:
    joined = " ".join(frames)
    if blocking_site.startswith(("xfs_", "xlog_")) or "xfs_" in joined:
        return "xfs"
    if blocking_site in {"blk_mq_get_tag", "submit_bio", "io_schedule"} or "nvme_" in joined:
        return "block_io"
    if blocking_site.startswith("rwsem_") or blocking_site == "mutex_lock":
        return "generic_lock"
    if "nfs_" in joined or "rpc_" in joined or "xprt_" in joined:
        return "nfs_rpc"
    if "rcu_" in joined:
        return "rcu"
    return "unknown"


def parse_tasks(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    starts = [(number, match) for number, line in enumerate(lines, start=1)
              if (match := TASK_HEADER.match(line))]
    tasks = []
    for index, (start_line, header) in enumerate(starts):
        end_line = starts[index + 1][0] - 1 if index + 1 < len(starts) else len(lines)
        frames = [match.group("name") for line in lines[start_line:end_line]
                  if (match := FRAME.match(line))]
        blocking_site = next((name for name in frames if name in BLOCKING_SITES), "unknown")
        subsystem = subsystem_for(frames, blocking_site)
        tasks.append({
            "pid": int(header.group("pid")), "task": header.group("task"),
            "comm": header.group("comm"), "blocking_site": blocking_site,
            "subsystems": [] if subsystem == "unknown" else [subsystem],
            "stack_fingerprint": hashlib.sha256(">".join(frames).encode()).hexdigest()[:16],
            "raw_span": {"start_line": start_line, "end_line": end_line},
        })
    return tasks


def build_routing(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[tuple[str, str]] = Counter()
    unique_pids: dict[tuple[str, str], set[int]] = {}
    for task in tasks:
        key = (task["subsystems"][0] if task["subsystems"] else "unknown", task["blocking_site"])
        counts[key] += 1
        unique_pids.setdefault(key, set()).add(task["pid"])
    groups = [{"subsystem": subsystem, "blocking_site": site,
               "count": len(unique_pids[(subsystem, site)]), "raw_record_count": raw_count}
              for (subsystem, site), raw_count in sorted(counts.items())]
    xfs_pids = sorted({task["pid"] for task in tasks
                       if "xfs" in task["subsystems"] and task["blocking_site"] == "xfs_buf_lock"})
    routes = ([{"name": "xfs_hang", "candidate_pids": xfs_pids,
                "reason": "xfs buffer lock waiters detected"}] if xfs_pids else [])
    return {"groups": groups, "routes": routes}


def primary_class(text: str, routing: dict[str, Any]) -> str:
    if FAULT_SIGNATURE.search(SYSRQ_CRASH.sub("", text)):
        return "oops_panic"
    if any(route["name"] == "xfs_hang" for route in routing["routes"]):
        return "xfs_hang"
    return "hung_task" if routing["groups"] else "unknown"


def _write_focus(output_dir: Path, text: str, routing: dict[str, Any], classification: dict[str, Any]) -> None:
    focus = output_dir / "focus"
    focus.mkdir(exist_ok=True)
    patterns = []
    if any(route["name"] == "xfs_hang" for route in routing["routes"]):
        patterns.append(("xfs.txt", r"xfs|inodegc|xlog|TASK_UNINTERRUPTIBLE|^PID:|^COMMAND:"))
    if classification["primary_class"] == "oops_panic":
        patterns.append(("fault.txt", r"BUG:|Oops|WARNING|PANIC|RIP:|Call Trace"))
    if routing["groups"] and classification["primary_class"] != "xfs_hang":
        patterns.append(("hang.txt", r"TASK_UNINTERRUPTIBLE|blocked for more than|schedule|wait|^PID:|^COMMAND:"))
    for name, pattern in patterns:
        lines = [line for line in text.splitlines() if re.search(pattern, line, re.IGNORECASE)]
        if lines:
            (focus / name).write_text("\n".join(lines) + "\n")


def classify_collection(collection_path: Path) -> dict[str, Any]:
    """Build pre-analysis artifacts from a successful collection handoff."""
    try:
        collection = json.loads(collection_path.read_text())
        raw_path = Path(collection["crash_raw"])
        output_dir = Path(collection["output_dir"])
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise ClassificationError(f"invalid collection file: {collection_path}") from error
    if not raw_path.is_file():
        raise ClassificationError(f"crash output is not readable: {raw_path}")
    text = raw_path.read_text(errors="replace")
    tasks = parse_tasks(text)
    routing = build_routing(tasks)
    classification = {"schema_version": 1, "primary_class": primary_class(text, routing),
                      "capture_trigger": "sysrq_crash" if SYSRQ_CRASH.search(text) else None}
    task_index = {"schema_version": 1, "source": "crash", "task_count": len(tasks), "tasks": tasks}
    routing_document = {"schema_version": 1, **routing}
    for name, document in (("task-index.json", task_index), ("routing.json", routing_document),
                           ("classification.json", classification)):
        (output_dir / name).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    inputs = collection["inputs"]
    evidence = {"schema_version": 1, "inputs": {
        "vmcore": inputs["vmcore"], "vmlinux": collection["vmlinux"], "kernel": inputs["kernel"],
        "dmesg": inputs.get("dmesg"),
    }, "classification": classification, "routes": routing["routes"],
        "groups": routing["groups"], "tasks": tasks}
    (output_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    _write_focus(output_dir, text, routing, classification)
    (output_dir / "queries.log").write_text("")
    (output_dir / "analysis.md").write_text(
        "# vmcore evidence bundle\n\nEvidence was collected. Use the matching analysis skill for iterative verification.\n"
    )
    return evidence
