from pathlib import Path


def test_click_command_modules_defer_annotations_for_python_39():
    source_root = Path(__file__).parents[1] / "src/crashanalysis_cli/commands"

    for name in ("vmcore.py", "skills.py"):
        source = (source_root / name).read_text()
        assert "from __future__ import annotations" in source
