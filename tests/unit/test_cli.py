from typer.testing import CliRunner

from web_crawler.cli import app

runner = CliRunner()


def test_cli_prints_web_crawler():
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "Web Crawler" in result.output
