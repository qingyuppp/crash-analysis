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
    assert result.output.strip() == str(tmp_path / "evidence.json")
