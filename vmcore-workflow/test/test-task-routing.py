#!/usr/bin/env python3
"""Tests for all-UN task discovery and specialist routing."""

import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "lib" / "classify_evidence.py"
FIXTURE = ROOT / "test" / "fixtures" / "un-routing-crash.txt"


class TaskRoutingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = pathlib.Path(self.tmp.name)
        subprocess.run(
            ["python3", SCRIPT, "--crash", FIXTURE, "--out-dir", self.output],
            check=True,
            text=True,
            capture_output=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_keeps_every_un_task_without_full_stack(self):
        index = json.loads((self.output / "task-index.json").read_text())
        self.assertEqual(index["task_count"], 4)
        task = index["tasks"][0]
        self.assertEqual(task["pid"], 73713)
        self.assertEqual(task["blocking_site"], "xfs_buf_lock")
        self.assertIn("xfs", task["subsystems"])
        self.assertIn("raw_span", task)
        self.assertNotIn("frames", task)

    def test_routing_groups_subsystems_without_claiming_root_cause(self):
        routing = json.loads((self.output / "routing.json").read_text())
        groups = {(group["subsystem"], group["blocking_site"]): group["count"]
                  for group in routing["groups"]}
        self.assertEqual(groups[("xfs", "xfs_buf_lock")], 2)
        self.assertEqual(groups[("block_io", "blk_mq_get_tag")], 1)
        self.assertEqual(groups[("generic_lock", "rwsem_down_write_slowpath")], 1)
        self.assertEqual(routing["routes"], [{
            "candidate_pids": [73713, 318156],
            "name": "xfs_hang",
            "reason": "xfs buffer lock waiters detected",
        }])

    def test_routing_deduplicates_xfs_candidates_from_second_pass_stacks(self):
        crash = self.output / "duplicated-xfs-stacks.txt"
        output = self.output / "duplicated-xfs-stacks.out"
        crash.write_text(FIXTURE.read_text() + FIXTURE.read_text())
        subprocess.run(
            ["python3", SCRIPT, "--crash", crash, "--out-dir", output],
            check=True,
            text=True,
            capture_output=True,
        )
        routing = json.loads((output / "routing.json").read_text())
        self.assertEqual(routing["routes"][0]["candidate_pids"], [73713, 318156])

    def test_routing_groups_count_unique_tasks_and_expose_raw_records(self):
        crash = self.output / "duplicated-xfs-groups.txt"
        output = self.output / "duplicated-xfs-groups.out"
        crash.write_text(FIXTURE.read_text() + FIXTURE.read_text())
        subprocess.run(
            ["python3", SCRIPT, "--crash", crash, "--out-dir", output],
            check=True,
            text=True,
            capture_output=True,
        )
        routing = json.loads((output / "routing.json").read_text())
        group = next(group for group in routing["groups"]
                     if group["subsystem"] == "xfs"
                     and group["blocking_site"] == "xfs_buf_lock")
        self.assertEqual(group["count"], 2)
        self.assertEqual(group["raw_record_count"], 4)

    def classify_text(self, name, text):
        crash = self.output / name
        output = self.output / f"{name}.out"
        crash.write_text(text)
        subprocess.run(
            ["python3", SCRIPT, "--crash", crash, "--out-dir", output],
            check=True,
            text=True,
            capture_output=True,
        )
        return json.loads((output / "classification.json").read_text())

    def test_sysrq_capture_panic_does_not_hide_xfs_hang(self):
        classification = self.classify_text(
            "sysrq-xfs.txt",
            FIXTURE.read_text() +
            '\nPANIC: "Kernel panic - not syncing: sysrq triggered crash"\n',
        )
        self.assertEqual(classification["primary_class"], "xfs_hang")
        self.assertEqual(classification["capture_trigger"], "sysrq_crash")

    def test_real_oops_before_sysrq_remains_primary_fault(self):
        classification = self.classify_text(
            "oops-before-sysrq.txt",
            "Oops: synthetic fault\n" + FIXTURE.read_text() +
            '\nPANIC: "Kernel panic - not syncing: sysrq triggered crash"\n',
        )
        self.assertEqual(classification["primary_class"], "oops_panic")
        self.assertEqual(classification["capture_trigger"], "sysrq_crash")


if __name__ == "__main__":
    unittest.main()
