import json
from pathlib import Path

from click.testing import CliRunner


RAW_XFS = '''Kernel panic - not syncing: sysrq triggered crash
PID: 42 TASK: ffff COMMAND: "xfs-worker"
 #0 [ffff] xfs_buf_lock
 #1 [ffff] xfs_buf_delwri_submit
PID: 0 TASK: idle COMMAND: "swapper/0"
 #0 [ffff] cpu_startup_entry
'''


def test_classify_collection_writes_xfs_route_and_evidence_bundle(tmp_path: Path):
    from crashanalysis_cli.classification import classify_collection

    raw = tmp_path / "crash-raw.txt"
    raw.write_text(RAW_XFS)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    collection_path = output_dir / "collection.json"
    collection_path.write_text(json.dumps({
        "schema_version": 1,
        "inputs": {"vmcore": "/in/vmcore", "kernel": "/in/kernel", "dmesg": None},
        "output_dir": str(output_dir),
        "vmlinux": "/debug/vmlinux",
        "crash_raw": str(raw),
        "crash_commands": str(output_dir / "crash.cmds"),
    }))

    evidence = classify_collection(collection_path)

    assert evidence["classification"] == {
        "capture_trigger": "sysrq_crash", "primary_class": "xfs_hang", "schema_version": 1
    }
    assert evidence["routes"] == [{
        "candidate_pids": [42], "name": "xfs_hang", "reason": "xfs buffer lock waiters detected"
    }]
    assert evidence["groups"] == [
        {"subsystem": "unknown", "blocking_site": "unknown", "candidate_pids": [0],
         "count": 1, "raw_record_count": 1},
        {"subsystem": "xfs", "blocking_site": "xfs_buf_lock", "candidate_pids": [42],
         "count": 1, "raw_record_count": 1},
    ]
    assert evidence["tasks"][1]["comm"] == "swapper/0"
    assert json.loads((output_dir / "evidence.json").read_text()) == evidence
    assert (output_dir / "focus/xfs.txt").is_file()
    assert (output_dir / "queries.log").read_text() == ""
    assert "Evidence was collected" in (output_dir / "analysis.md").read_text()


def test_classify_command_prints_evidence_artifact_path(tmp_path: Path):
    from crashanalysis_cli.main import cli

    raw = tmp_path / "crash-raw.txt"
    raw.write_text(RAW_XFS)
    collection = tmp_path / "collection.json"
    collection.write_text(json.dumps({
        "schema_version": 1,
        "inputs": {"vmcore": "/in/vmcore", "kernel": "/in/kernel", "dmesg": None},
        "output_dir": str(tmp_path), "vmlinux": "/debug/vmlinux", "crash_raw": str(raw),
        "crash_commands": str(tmp_path / "crash.cmds"),
    }))

    result = CliRunner().invoke(cli, ["vmcore", "classify", "--collection", str(collection)])

    assert result.exit_code == 0
    assert "Groups:" in result.output
    assert "xfs / xfs_buf_lock: 1 PID [42]" in result.output
    assert "Suggested routes:" in result.output
    assert "xfs_hang: PIDs [42] reason: xfs buffer lock waiters detected" in result.output
    assert result.output.rstrip().endswith(str(tmp_path / "evidence.json"))


def test_routing_groups_keep_all_pids_but_summary_limits_display_to_twenty():
    from crashanalysis_cli.classification import build_routing, format_routing_summary

    tasks = [
        {"pid": pid, "subsystems": ["xfs"], "blocking_site": "xfs_buf_lock"}
        for pid in range(1, 22)
    ]
    routing = build_routing(tasks)

    assert routing["groups"] == [{
        "subsystem": "xfs", "blocking_site": "xfs_buf_lock",
        "candidate_pids": list(range(1, 22)), "count": 21, "raw_record_count": 21,
    }]
    assert routing["routes"][0]["candidate_pids"] == list(range(1, 22))
    assert "xfs / xfs_buf_lock: 21 PIDs [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20] (+1 more; see evidence.json)" in format_routing_summary(routing)
