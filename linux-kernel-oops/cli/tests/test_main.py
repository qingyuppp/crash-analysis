from click.testing import CliRunner


def test_root_help_lists_vmcore_and_skills_groups():
    from crashanalysis_cli.main import cli

    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "vmcore" in result.output
    assert "skills" in result.output


def test_banner_is_shown_only_on_root_help():
    from crashanalysis_cli.main import cli

    runner = CliRunner()
    root_help = runner.invoke(cli, ["--help"])
    vmcore_help = runner.invoke(cli, ["vmcore", "--help"])

    assert root_help.exit_code == 0
    assert "CrashAnalysis" in root_help.output
    assert "\n   ____               _       _                _           _\n" in root_help.output
    assert vmcore_help.exit_code == 0
    assert "CrashAnalysis" not in vmcore_help.output
