import json
import subprocess
from pathlib import Path


def test_collect_writes_fixed_crash_commands_and_handoff(tmp_path: Path):
    from crashanalysis_cli.collection import CollectionInputs, collect_vmcore

    vmcore = tmp_path / "vmcore"
    debuginfo = tmp_path / "debuginfo.rpm"
    kernel = tmp_path / "kernel"
    vmcore.write_text("vmcore")
    debuginfo.write_text("rpm")
    kernel.mkdir()
    calls = []

    def fake_run(args, *, cwd=None, input_bytes=None):
        calls.append((args, cwd, input_bytes))
        if args[0] == "rpm2cpio":
            return subprocess.CompletedProcess(args, 0, stdout=b"cpio-data", stderr=b"")
        if args[0] == "cpio":
            vmlinux = Path(cwd) / "usr/lib/debug/lib/modules/test/vmlinux"
            vmlinux.parent.mkdir(parents=True)
            vmlinux.write_text("symbols")
            return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")
        assert args[0] == "crash"
        return subprocess.CompletedProcess(args, 0, stdout=b"PID: 1 TASK: abc COMMAND: \"test\"\n", stderr=b"")

    output_dir = tmp_path / "output"
    collection = collect_vmcore(
        CollectionInputs(vmcore=vmcore, debuginfo=debuginfo, kernel=kernel, output_dir=output_dir),
        run=fake_run,
    )

    assert (output_dir / "crash.cmds").read_text().splitlines() == [
        "set scroll off", "sys", "log", "ps -m", "bt -a", "foreach UN bt", "mod", "mount", "kmem -i", "exit"
    ]
    assert (output_dir / "crash-raw.txt").read_text() == 'PID: 1 TASK: abc COMMAND: "test"\n'
    assert collection["schema_version"] == 1
    assert collection["inputs"]["vmcore"] == str(vmcore)
    assert Path(collection["vmlinux"]).is_file()
    assert json.loads((output_dir / "collection.json").read_text()) == collection
    assert [call[0][0] for call in calls] == ["rpm2cpio", "cpio", "crash"]
