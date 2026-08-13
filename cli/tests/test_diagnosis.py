import json
from pathlib import Path

from click.testing import CliRunner


def make_evidence(tmp_path: Path) -> Path:
    vmlinux = tmp_path / "vmlinux"
    vmcore = tmp_path / "vmcore"
    vmlinux.write_text("symbols")
    vmcore.write_text("dump")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "schema_version": 1,
        "inputs": {"vmlinux": str(vmlinux), "vmcore": str(vmcore)},
    }))
    return evidence


def fake_crash(args, *, cwd=None, input_bytes=None):
    import subprocess

    command_file = Path(args[args.index("-i") + 1])
    commands = command_file.read_text()
    return subprocess.CompletedProcess(
        args, 0,
        stdout=("PID: 42 TASK: ffff COMMAND: \"worker\"\n"
                " #0 [ffff] xfs_buf_lock\n"
                " #1 [ffff] xfs_read_agf\n").encode(),
        stderr=b"",
    )


def test_query_writes_individual_artifact_and_appends_queries_log(tmp_path: Path):
    from crashanalysis_cli.diagnosis import diagnose_query

    evidence = make_evidence(tmp_path)
    result = diagnose_query(evidence, "bt -f 42", run=fake_crash)

    action_dir = tmp_path / "actions" / "001-query"
    assert result["status"] == "ok"
    assert result["action"] == "query"
    assert (action_dir / "request.json").is_file()
    assert (action_dir / "commands.txt").read_text() == "bt -f 42\nexit\n"
    assert (action_dir / "raw.txt").read_text().startswith("PID: 42")
    assert (action_dir / "result.json").is_file()
    assert "bt -f 42" in (tmp_path / "queries.log").read_text()


def test_high_level_actions_build_fixed_crash_commands(tmp_path: Path):
    from crashanalysis_cli.diagnosis import diagnose_compact_bt, diagnose_structure, diagnose_symbol, diagnose_task

    evidence = make_evidence(tmp_path)
    calls = []

    def run(args, **kwargs):
        calls.append(Path(args[args.index("-i") + 1]).read_text())
        return fake_crash(args, **kwargs)

    diagnose_compact_bt(evidence, [3, 2], run=run)
    diagnose_task(evidence, 9, run=run)
    diagnose_structure(evidence, "xfs_buf", "0xffff1234", run=run)
    diagnose_symbol(evidence, "xfs_mount", run=run)

    assert calls[0] == "bt 3\nbt 2\nexit\n"
    assert calls[1] == "bt -f 9\nexit\n"
    assert calls[2] == "struct xfs_buf 0xffff1234\nexit\n"
    assert calls[3] == "p xfs_mount\nexit\n"


def test_compact_bt_parses_xfs_kinds_into_result_observations(tmp_path: Path):
    from crashanalysis_cli.diagnosis import diagnose_compact_bt

    evidence = make_evidence(tmp_path)

    def run(args, **kwargs):
        import subprocess

        return subprocess.CompletedProcess(args, 0, stdout=(
            'PID: 3 TASK: t3 COMMAND: "agi-worker"\n'
            ' #0 [ffff] xfs_buf_lock\n'
            ' #1 [ffff] xfs_read_agi\n'
            'PID: 2 TASK: t2 COMMAND: "agf-worker"\n'
            ' #0 [ffff] xfs_buf_lock\n'
            ' #1 [ffff] xfs_read_agf\n'
            'PID: 1 TASK: t1 COMMAND: "inode-worker"\n'
            ' #0 [ffff] xfs_buf_lock\n'
            ' #1 [ffff] xfs_imap_to_bp\n'
            'PID: 4 TASK: t4 COMMAND: "other-worker"\n'
            ' #0 [ffff] xfs_buf_lock\n'
            ' #1 [ffff] xfs_buf_find\n'
        ).encode(), stderr=b"")

    result = diagnose_compact_bt(evidence, [3, 2, 1, 4, 99], run=run)

    assert result["status"] == "partial"
    assert result["observations"]["direct_xfs_buf_lock_waiters"] == 4
    assert result["observations"]["requested_pids"] == [3, 2, 1, 4, 99]
    assert result["observations"]["parsed_pids"] == [1, 2, 3, 4]
    assert result["observations"]["missing_pids"] == [99]
    assert result["observations"]["groups"] == [
        {"kind": "agi", "pids": [3], "commands": ["agi-worker"],
         "frames": ["xfs_buf_lock", "xfs_read_agi"]},
        {"kind": "agf", "pids": [2], "commands": ["agf-worker"],
         "frames": ["xfs_buf_lock", "xfs_read_agf"]},
        {"kind": "inode_cluster", "pids": [1], "commands": ["inode-worker"],
         "frames": ["xfs_buf_lock", "xfs_imap_to_bp"]},
        {"kind": "other", "pids": [4], "commands": ["other-worker"],
         "frames": ["xfs_buf_lock", "xfs_buf_find"]},
    ]


def test_diagnose_commands_are_registered(tmp_path: Path):
    from crashanalysis_cli.main import cli

    result = CliRunner().invoke(cli, ["vmcore", "diagnose", "--help"])

    assert result.exit_code == 0
    for command in ("query", "compact-bt", "task", "structure", "symbol"):
        assert command in result.output
