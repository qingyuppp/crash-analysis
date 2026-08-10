"""Bundled-skill Click commands."""

from pathlib import Path

import click

from crashanalysis_cli.main import skills
from crashanalysis_cli.skills import (
    SkillTargetError, install_skill, list_skills, resolve_target_dir, show_skill, uninstall_skill,
)


def _target_options(function):
    function = click.option("--skills-dir", type=click.Path(path_type=Path))(function)
    return click.option("--target", type=click.Choice(["joycode", "codex", "custom"]), default="joycode")(function)


@skills.command("list")
@_target_options
def list_command(target: str, skills_dir: Path | None) -> None:
    """List skills shipped with this CLI."""
    for item in list_skills():
        click.echo(f'{item["name"]}\t{item["description"]}')


@skills.command("show")
@click.argument("name")
def show_command(name: str) -> None:
    """Print a bundled skill's entry file."""
    try:
        click.echo(show_skill(name), nl=False)
    except ValueError as error:
        raise click.ClickException(str(error)) from error


@skills.command("install")
@click.argument("name")
@click.option("--force", is_flag=True, help="Replace an existing destination skill.")
@_target_options
def install_command(name: str, force: bool, target: str, skills_dir: Path | None) -> None:
    """Copy one bundled skill to a target skill directory."""
    try:
        destination = install_skill(name, target_dir=resolve_target_dir(target, skills_dir), force=force)
    except (ValueError, FileExistsError, SkillTargetError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(destination)


@skills.command("uninstall")
@click.argument("name")
@_target_options
def uninstall_command(name: str, target: str, skills_dir: Path | None) -> None:
    """Remove a skill previously installed by this CLI."""
    try:
        destination = uninstall_skill(name, resolve_target_dir(target, skills_dir))
    except (ValueError, SkillTargetError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(destination)
