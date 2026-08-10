"""Bundled skill discovery and safe local installation."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional


REGISTRY_NAME = ".cra-installed-skills.json"
SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class SkillTargetError(ValueError):
    """A skill target is missing or unsupported."""


def bundled_skill_root() -> Path:
    return Path(__file__).parent / "skills"


def _validate_name(name: str) -> None:
    if not SKILL_NAME.fullmatch(name):
        raise ValueError(f"invalid skill name: {name}")


def _skill_path(name: str, source_root: Path) -> Path:
    _validate_name(name)
    path = source_root / name
    if not (path / "SKILL.md").is_file():
        raise ValueError(f"unknown bundled skill: {name}")
    return path


def _description(skill_file: Path) -> str:
    match = re.search(r"^description:\s*[\"']?(.*?)[\"']?\s*$", skill_file.read_text(), re.MULTILINE)
    return match.group(1) if match else ""


def list_skills(source_root: Optional[Path] = None) -> list[dict[str, str]]:
    root = source_root or bundled_skill_root()
    return [{"name": child.name, "description": _description(child / "SKILL.md")}
            for child in sorted(root.iterdir()) if child.is_dir() and (child / "SKILL.md").is_file()]


def show_skill(name: str, source_root: Optional[Path] = None) -> str:
    return (_skill_path(name, source_root or bundled_skill_root()) / "SKILL.md").read_text()


def resolve_target_dir(target: str, skills_dir: Optional[Path] = None) -> Path:
    if skills_dir is not None:
        return skills_dir
    if target == "joycode":
        return Path(os.environ.get("JOYCODE_SKILLS_DIR", "/root/.joycode/skills"))
    if target == "codex":
        codex_home = os.environ.get("CODEX_HOME")
        return Path(codex_home) / "skills" if codex_home else Path.home() / ".codex" / "skills"
    if target == "custom":
        raise SkillTargetError("target custom requires --skills-dir")
    raise SkillTargetError(f"unsupported skill target: {target}")


def _load_registry(target_dir: Path) -> dict[str, list[str]]:
    registry = target_dir / REGISTRY_NAME
    if not registry.is_file():
        return {"skills": []}
    try:
        value = json.loads(registry.read_text())
        if not isinstance(value.get("skills"), list):
            raise ValueError
        return value
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SkillTargetError(f"invalid skill registry: {registry}") from error


def _save_registry(target_dir: Path, registry: dict[str, list[str]]) -> None:
    (target_dir / REGISTRY_NAME).write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def install_skill(name: str, *, source_root: Optional[Path] = None, target_dir: Path,
                  force: bool = False) -> Path:
    source = _skill_path(name, source_root or bundled_skill_root())
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / name
    if destination.exists() and not force:
        raise FileExistsError(f"skill already exists: {destination}; use --force to replace it")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    registry = _load_registry(target_dir)
    if name not in registry["skills"]:
        registry["skills"].append(name)
        registry["skills"].sort()
    _save_registry(target_dir, registry)
    return destination


def uninstall_skill(name: str, target_dir: Path) -> Path:
    _validate_name(name)
    registry = _load_registry(target_dir)
    if name not in registry["skills"]:
        raise SkillTargetError(f"skill is not installed by cra: {name}")
    destination = target_dir / name
    if destination.is_dir():
        shutil.rmtree(destination)
    registry["skills"].remove(name)
    _save_registry(target_dir, registry)
    return destination
