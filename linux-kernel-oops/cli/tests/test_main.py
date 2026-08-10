from click.testing import CliRunner


def test_root_help_lists_vmcore_and_skills_groups():
    from crashanalysis_cli.main import cli

    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "vmcore" in result.output
    assert "skills" in result.output
