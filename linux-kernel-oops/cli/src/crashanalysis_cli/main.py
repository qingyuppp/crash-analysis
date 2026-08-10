"""The root command for the crash-analysis CLI."""

import click


@click.group()
def cli() -> None:
    """Collect and classify deterministic Linux vmcore evidence."""


@cli.group()
def vmcore() -> None:
    """Collect and classify vmcore evidence."""


@cli.group()
def skills() -> None:
    """Inspect and install bundled analysis skills."""


from crashanalysis_cli.commands import vmcore as _vmcore  # noqa: E402,F401
from crashanalysis_cli.commands import skills as _skills  # noqa: E402,F401


if __name__ == "__main__":
    cli()
