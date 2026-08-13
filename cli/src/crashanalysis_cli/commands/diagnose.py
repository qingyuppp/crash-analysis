"""Follow-up vmcore diagnostic commands."""

from __future__ import annotations

from pathlib import Path

import click

from crashanalysis_cli.diagnosis import (
    DiagnosisError, diagnose_compact_bt, diagnose_query, diagnose_structure,
    diagnose_symbol, diagnose_task,
)
from crashanalysis_cli.main import diagnose


def _emit(function):
    return click.option("--evidence", type=click.Path(path_type=Path), required=True)(function)


@diagnose.command("query")
@click.option("--command", "command_text", required=True)
@_emit
def query(evidence: Path, command_text: str) -> None:
    """Execute one crash command and save its result."""
    try:
        result = diagnose_query(evidence, command_text)
    except DiagnosisError as error:
        raise click.ClickException(str(error)) from error
    click.echo(result["raw_artifact"])


@diagnose.command("compact-bt")
@click.option("--pids", required=True, help="Comma-separated PID list.")
@_emit
def compact_bt(evidence: Path, pids: str) -> None:
    """Collect compact backtraces for multiple PIDs."""
    try:
        values = [int(value.strip()) for value in pids.split(",") if value.strip()]
        result = diagnose_compact_bt(evidence, values)
    except (ValueError, DiagnosisError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(result["raw_artifact"])


@diagnose.command("task")
@click.option("--pid", type=int, required=True)
@_emit
def task(evidence: Path, pid: int) -> None:
    """Collect a full backtrace for one PID."""
    try:
        result = diagnose_task(evidence, pid)
    except DiagnosisError as error:
        raise click.ClickException(str(error)) from error
    click.echo(result["raw_artifact"])


@diagnose.command("structure")
@click.option("--type", "structure_type", required=True)
@click.option("--address", required=True)
@_emit
def structure(evidence: Path, structure_type: str, address: str) -> None:
    """Inspect a kernel structure at an address."""
    try:
        result = diagnose_structure(evidence, structure_type, address)
    except DiagnosisError as error:
        raise click.ClickException(str(error)) from error
    click.echo(result["raw_artifact"])


@diagnose.command("symbol")
@click.option("--name", required=True)
@_emit
def symbol(evidence: Path, name: str) -> None:
    """Inspect a crash symbol or global expression."""
    try:
        result = diagnose_symbol(evidence, name)
    except DiagnosisError as error:
        raise click.ClickException(str(error)) from error
    click.echo(result["raw_artifact"])
