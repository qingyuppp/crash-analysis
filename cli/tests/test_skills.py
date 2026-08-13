import os
from pathlib import Path

import pytest


def test_skill_install_list_show_and_registered_uninstall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from crashanalysis_cli.skills import (
        install_skill, list_skills, resolve_target_dir, show_skill, uninstall_skill,
    )

    source_root = tmp_path / "bundled"
    skill = source_root / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: demo\ndescription: Demo skill\n---\n\n# Demo\n")
    target = tmp_path / "joycode-skills"
    monkeypatch.setenv("JOYCODE_SKILLS_DIR", str(target))

    assert list_skills(source_root) == [{"name": "demo", "description": "Demo skill"}]
    assert "# Demo" in show_skill("demo", source_root)
    assert resolve_target_dir("joycode") == target
    installed = install_skill("demo", source_root=source_root, target_dir=target)
    assert installed == target / "demo"
    assert (target / "demo" / "SKILL.md").is_file()
    with pytest.raises(FileExistsError):
        install_skill("demo", source_root=source_root, target_dir=target)
    assert uninstall_skill("demo", target) == target / "demo"
    assert not (target / "demo").exists()


def test_custom_target_requires_explicit_path():
    from crashanalysis_cli.skills import SkillTargetError, resolve_target_dir

    with pytest.raises(SkillTargetError, match="--skills-dir"):
        resolve_target_dir("custom")
