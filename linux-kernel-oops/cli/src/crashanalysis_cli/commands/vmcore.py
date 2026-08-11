"""Vmcore Click commands."""

from __future__ import annotations

from pathlib import Path

import click

from crashanalysis_cli.collection import CollectionError, CollectionInputs, collect_vmcore
from crashanalysis_cli.classification import (
    ClassificationError,
    classify_collection,
    format_routing_summary,
)
from crashanalysis_cli.main import vmcore


@vmcore.command("collect")
@click.option("--vmcore", type=click.Path(path_type=Path), required=True)
@click.option("--debuginfo", type=click.Path(path_type=Path), required=True)
@click.option("--kernel", type=click.Path(path_type=Path), required=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--dmesg", type=click.Path(path_type=Path))
def collect(vmcore: Path, debuginfo: Path, kernel: Path, output_dir: Path,
            dmesg: Path | None) -> None:
    """Run fixed first-pass crash collection."""
    try:
        result = collect_vmcore(CollectionInputs(vmcore, debuginfo, kernel, output_dir, dmesg))
    except CollectionError as error:
        raise click.ClickException(str(error)) from error
    click.echo(result["crash_raw"])


@vmcore.command("classify")
@click.option("--collection", "collection_path", type=click.Path(path_type=Path), required=True)
def classify(collection_path: Path) -> None:
    """Build routing evidence from a previous collection."""
    try:
        evidence = classify_collection(collection_path)
    except ClassificationError as error:
        raise click.ClickException(str(error)) from error
    click.echo(format_routing_summary(evidence))
    click.echo(str(collection_path.parent / "evidence.json"))
