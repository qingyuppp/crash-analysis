#!/usr/bin/env python3
"""Build a bounded task index and routing decision from crash text.

This program deliberately consumes exported crash text only.  It does not open
vmcore files and its output is evidence routing, not a root-cause conclusion.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


TASK_HEADER = re.compile(
    r'^PID:\s*(?P<pid>\d+)\s+TASK:\s*(?P<task>\S+).*?COMMAND:\s*"(?P<comm>[^"]+)"'
)
FRAME = re.compile(r'^\s*#\d+\s+\[[^]]+\]\s+(?P<name>[^\s+]+)')
SYSRQ_CRASH = re.compile(
    r'^.*Kernel panic - not syncing: sysrq triggered crash.*(?:\n|$)',
    re.IGNORECASE | re.MULTILINE,
)
FAULT_SIGNATURE = re.compile(
    r'\b(?:Kernel panic\b|Oops:|BUG:|WARNING:)',
    re.IGNORECASE,
)

BLOCKING_SITES = (
    "xfs_buf_lock",
    "xlog_grant_head_wait",
    "blk_mq_get_tag",
    "submit_bio",
    "io_schedule",
    "rwsem_down_write_slowpath",
    "rwsem_down_read_slowpath",
    "mutex_lock",
    "wait_for_completion",
)

XFS_BUFFER_NEXT_COMMANDS = [
    "bt -f <xfs candidate pid>",
    "derive an xfs_buf base address from the b_sema offset",
    "struct xfs_buf.b_ops <derived xfs_buf>",
    "struct xfs_buf.b_log_item <derived xfs_buf>",
]


def subsystem_for(frames, blocking_site):
    joined = " ".join(frames)
    if blocking_site.startswith("xfs_") or blocking_site.startswith("xlog_") or "xfs_" in joined:
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


def parse_tasks(text):
    lines = text.splitlines()
    starts = []
    for number, line in enumerate(lines, start=1):
        match = TASK_HEADER.match(line)
        if match:
            starts.append((number, match))

    tasks = []
    for index, (start_line, header) in enumerate(starts):
        end_line = starts[index + 1][0] - 1 if index + 1 < len(starts) else len(lines)
        frames = []
        for line in lines[start_line:end_line]:
            match = FRAME.match(line)
            if match:
                frames.append(match.group("name"))
        blocking_site = next((name for name in frames if name in BLOCKING_SITES), "unknown")
        subsystem = subsystem_for(frames, blocking_site)
        fingerprint = ">".join(frames)
        tasks.append({
            "pid": int(header.group("pid")),
            "task": header.group("task"),
            "comm": header.group("comm"),
            "blocking_site": blocking_site,
            "subsystems": [] if subsystem == "unknown" else [subsystem],
            "stack_fingerprint": hashlib.sha256(fingerprint.encode()).hexdigest()[:16],
            "raw_span": {"start_line": start_line, "end_line": end_line},
        })
    return tasks


def build_routing(tasks):
    counts = Counter()
    unique_pids = {}
    for task in tasks:
        key = (task["subsystems"][0] if task["subsystems"] else "unknown",
               task["blocking_site"])
        counts[key] += 1
        unique_pids.setdefault(key, set()).add(task["pid"])
    groups = [
        {
            "subsystem": subsystem,
            "blocking_site": site,
            "count": len(unique_pids[(subsystem, site)]),
            "raw_record_count": raw_count,
        }
        for (subsystem, site), raw_count in sorted(counts.items())
    ]
    xfs_pids = sorted({
        task["pid"] for task in tasks
        if "xfs" in task["subsystems"] and task["blocking_site"] == "xfs_buf_lock"
    })
    routes = []
    if xfs_pids:
        routes.append({
            "name": "xfs_hang",
            "candidate_pids": xfs_pids,
            "reason": "xfs buffer lock waiters detected",
        })
    return {"groups": groups, "routes": routes}


def primary_class(text, routing):
    # A SysRq crash is an operator-triggered kdump collection event, not an
    # oops/panic root cause.  Remove only that exact log line so genuine fault
    # signatures elsewhere in the same crash text keep their priority.
    fault_text = SYSRQ_CRASH.sub("", text)
    if FAULT_SIGNATURE.search(fault_text):
        return "oops_panic"
    if any(route["name"] == "xfs_hang" for route in routing["routes"]):
        return "xfs_hang"
    if routing["groups"]:
        return "hung_task"
    return "unknown"


def parse_xfs_edges(text):
    """Parse only explicit second-pass annotations, never inferred holders."""
    lines = text.splitlines()
    headers = [number for number, line in enumerate(lines) if TASK_HEADER.match(line)]
    edges = []
    for position, start in enumerate(headers):
        stop = headers[position + 1] if position + 1 < len(headers) else len(lines)
        header = TASK_HEADER.match(lines[start])
        fields = {}
        for line in lines[start + 1:stop]:
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        buffer_type = fields.get("BUFFER_TYPE")
        waited = fields.get("WAITS_FOR")
        if buffer_type not in {"AGF", "INODE_CLUSTER"} or not waited:
            continue
        item = {
            "waiter_pid": int(header.group("pid")),
            "waits_for": f"{buffer_type}:{waited[-6:].lower()}",
        }
        if fields.get("HELD_BY", "").isdigit():
            item["held_by"] = int(fields["HELD_BY"])
        edges.append(item)
    return sorted(edges, key=lambda edge: edge["waiter_pid"])


def xfs_graph(text):
    edges = parse_xfs_edges(text)
    kinds = {edge["waits_for"].split(":", 1)[0] for edge in edges}
    holders = {edge["waiter_pid"]: edge.get("held_by") for edge in edges}
    reciprocal = (len(edges) == 2 and kinds == {"AGF", "INODE_CLUSTER"} and
                  holders.get(edges[0]["waiter_pid"]) == edges[1]["waiter_pid"] and
                  holders.get(edges[1]["waiter_pid"]) == edges[0]["waiter_pid"])
    if reciprocal:
        verdict = "confirmed_agf_inode_abba"
        next_commands = []
    elif edges:
        verdict = "suspected_agf_inode_inversion"
        next_commands = XFS_BUFFER_NEXT_COMMANDS
    else:
        verdict = "insufficient_evidence_for_abba"
        next_commands = XFS_BUFFER_NEXT_COMMANDS
    return {"schema_version": 1, "verdict": verdict, "edges": edges,
            "next_commands": next_commands}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crash", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--source", default="crash")
    args = parser.parse_args()

    text = args.crash.read_text(errors="replace")
    tasks = parse_tasks(text)
    routing = build_routing(tasks)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "task-index.json").write_text(json.dumps({
        "schema_version": 1,
        "source": args.source,
        "task_count": len(tasks),
        "tasks": tasks,
    }, indent=2, sort_keys=True) + "\n")
    (args.out_dir / "routing.json").write_text(json.dumps({
        "schema_version": 1,
        **routing,
    }, indent=2, sort_keys=True) + "\n")
    (args.out_dir / "classification.json").write_text(json.dumps({
        "schema_version": 1,
        "primary_class": primary_class(text, routing),
        "capture_trigger": "sysrq_crash" if SYSRQ_CRASH.search(text) else None,
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
