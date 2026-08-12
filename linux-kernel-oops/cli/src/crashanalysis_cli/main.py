"""The root command for the crash-analysis CLI."""

import click


BANNER = r"""
   ____               _       _                _           _
  / ___|_ __ __ _ ___| |__   / \   _ __   __ _| |_   _ ___(_)___
 | |   | '__/ _` / __| '_ \ / _ \ | '_ \ / _` | | | | / __| / __|
 | |___| | | (_| \__ \ | | / ___ \| | | | (_| | | |_| \__ \ \__ \
  \____|_|  \__,_|___/_| |_/_/   \_\_| |_|\__,_|_|\__, |___/_|___/
                                                    |___/

  CrashAnalysis
"""


class BannerGroup(click.Group):
    """Root command group that prepends the CrashAnalysis banner to help."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        formatter.write(BANNER)
        super().format_help(ctx, formatter)


@click.group(cls=BannerGroup)
def cli() -> None:
    """Collect and classify deterministic Linux vmcore evidence."""


@cli.group()
def vmcore() -> None:
    """Collect and classify vmcore evidence."""


@vmcore.group()
def diagnose() -> None:
    """Run follow-up crash evidence queries."""


@cli.group()
def skills() -> None:
    """Inspect and install bundled analysis skills."""


from crashanalysis_cli.commands import vmcore as _vmcore  # noqa: E402,F401
from crashanalysis_cli.commands import skills as _skills  # noqa: E402,F401
from crashanalysis_cli.commands import diagnose as _diagnose  # noqa: E402,F401


if __name__ == "__main__":
    cli()
