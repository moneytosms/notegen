from unittest.mock import patch
from pathlib import Path

from typer.testing import CliRunner

from notes_gen.cli import _show_custom_help, app, main

runner = CliRunner()


def test_help_invokes_rich_display(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["notegen", "--help"])
    with patch("notes_gen.cli._show_custom_help") as mock_help:
        main()
    mock_help.assert_called_once()


def test_no_args_invokes_rich_display(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["notegen"])
    with patch("notes_gen.cli._show_custom_help") as mock_help:
        main()
    mock_help.assert_called_once()


def test_version_flag_prints_version(monkeypatch):
    monkeypatch.setattr("notes_gen.cli._get_version", lambda: "2.3.0")
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "2.3.0" in result.output


def test_rich_help_contains_key_sections(capsys):
    _show_custom_help()
    out = capsys.readouterr().out
    assert "config init" in out
    assert "config open" in out
    assert "COMMANDS" in out
    assert "SOURCE FLAGS" in out
    assert "CONFIG FILE" in out


def test_auto_detect_youtube_video(tmp_path):
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    with patch("notes_gen.sources.youtube.run_video_pipeline") as mock_run:
        mock_run.return_value = tmp_path / "notes.md"
        (tmp_path / "notes.md").write_text("content")
        runner.invoke(app, ["auto", url, "--output-dir", str(tmp_path)])
    mock_run.assert_called_once()


def test_auto_detect_youtube_playlist(tmp_path):
    url = "https://www.youtube.com/playlist?list=PLtest123"
    with patch("notes_gen.sources.youtube.run_playlist_pipeline") as mock_run:
        mock_run.return_value = tmp_path / "playlist" / "index.md"
        (tmp_path / "playlist").mkdir()
        (tmp_path / "playlist" / "index.md").write_text("content")
        runner.invoke(app, ["auto", url, "--output-dir", str(tmp_path)])
    mock_run.assert_called_once()


def test_auto_detect_web_url(tmp_path):
    url = "https://docs.python.org/3/"
    with patch("notes_gen.sources.web.run_web_crawl_pipeline") as mock_run:
        mock_run.return_value = tmp_path / "notes.md"
        (tmp_path / "notes.md").write_text("content")
        runner.invoke(app, ["auto", url, "--output-dir", str(tmp_path)])
    mock_run.assert_called_once()


def test_auto_detect_text_file(tmp_path):
    text_file = tmp_path / "transcript.txt"
    text_file.write_text("some content here")
    with patch("notes_gen.sources.text.run_text_pipeline") as mock_run:
        mock_run.return_value = tmp_path / "notes.md"
        (tmp_path / "notes.md").write_text("content")
        runner.invoke(app, ["auto", str(text_file), "--output-dir", str(tmp_path)])
    mock_run.assert_called_once()


def test_config_show_runs():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "model" in result.output


def test_config_init_suggests_open(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    fake_config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", fake_config_path)
    result = runner.invoke(app, ["config", "init"])
    assert result.exit_code == 0
    assert "config open" in result.output


def test_text_command_wired(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "sample_transcript.txt"
    with patch("notes_gen.sources.text.generate_notes", return_value=("## Notes\n\nContent.", [])):
        result = runner.invoke(app, ["text", str(fixture), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0


def test_config_open_creates_config_if_missing(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    fake_config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", fake_config_path)

    with (
        patch("notes_gen.cli.subprocess.run"),
        patch("notes_gen.cli.platform.system", return_value="Linux"),
    ):
        result = runner.invoke(app, ["config", "open"])

    assert result.exit_code == 0
    assert fake_config_path.exists()
    assert "Opening" in result.output


def test_subcommand_help_still_works():
    result = runner.invoke(app, ["video", "--help"])
    assert result.exit_code == 0
    assert "url" in result.output.lower()


def test_config_validate_passes_valid_config(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    fake_config_path = tmp_path / "config.yaml"
    fake_config_path.write_text(
        "model: groq/llama-3.3-70b-versatile\napi_keys:\n  groq:\n    - gsk_test123\n"
    )
    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", fake_config_path)
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0


def test_config_validate_fails_missing_config(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", tmp_path / "nonexistent.yaml")
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 1


def test_doctor_fails_api_error(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    fake_config_path = tmp_path / "config.yaml"
    fake_config_path.write_text(
        "model: groq/llama-3.3-70b-versatile\napi_keys:\n  groq:\n    - gsk_test\n"
    )
    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", fake_config_path)

    with patch("notes_gen.cli.litellm.completion", side_effect=Exception("401 Unauthorized")):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1


def test_dry_run_text_no_llm_call(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "sample_transcript.txt"
    with patch("notes_gen.sources.text.generate_notes") as mock_llm:
        result = runner.invoke(
            app,
            ["text", str(fixture), "--output-dir", str(tmp_path), "--dry-run", "--no-cache"],
        )

    mock_llm.assert_not_called()
    assert result.exit_code == 0
