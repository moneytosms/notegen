from unittest.mock import patch

from typer.testing import CliRunner

from notes_gen.cli import _show_rich_help, app, main

runner = CliRunner()


def test_help_invokes_rich_display(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["notegen", "--help"])
    with patch("notes_gen.cli._show_rich_help") as mock_help:
        main()
    mock_help.assert_called_once()


def test_no_args_invokes_rich_display(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["notegen"])
    with patch("notes_gen.cli._show_rich_help") as mock_help:
        main()
    mock_help.assert_called_once()


def test_rich_help_contains_key_sections(capsys):
    _show_rich_help()
    out = capsys.readouterr().out
    assert "config init" in out
    assert "config open" in out
    assert "USAGE" in out
    assert "OPTIONS" in out
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


def test_main_injects_auto_for_bare_url(monkeypatch):
    """main() inserts 'auto' when first arg is a bare URL."""
    import sys

    injected = []

    def fake_app():
        injected.extend(sys.argv[1:])

    monkeypatch.setattr("notes_gen.cli.app", fake_app)
    monkeypatch.setattr(sys, "argv", ["notegen", "https://www.youtube.com/watch?v=test"])
    main()
    assert injected[0] == "auto"
    assert injected[1] == "https://www.youtube.com/watch?v=test"


def test_main_does_not_inject_for_known_subcommand(monkeypatch):
    import sys

    injected = []

    def fake_app():
        injected.extend(sys.argv[1:])

    monkeypatch.setattr("notes_gen.cli.app", fake_app)
    monkeypatch.setattr(sys, "argv", ["notegen", "video", "https://youtube.com/watch?v=x"])
    main()
    assert injected[0] == "video"


def test_config_show_runs():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "model" in result.output
    assert "verbose" in result.output


def test_config_init_suggests_open(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    fake_config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", fake_config_path)
    result = runner.invoke(app, ["config", "init"])
    assert result.exit_code == 0
    assert "config open" in result.output


def test_text_command_wired(tmp_path):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "sample_transcript.txt"
    with patch("notes_gen.sources.text.generate_notes", return_value="## Notes\n\nContent."):
        result = runner.invoke(app, ["text", str(fixture), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Notes written to" in result.output


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


def test_config_open_does_not_overwrite_existing(tmp_path, monkeypatch):
    import notes_gen.cli as cli_mod

    fake_config_path = tmp_path / "config.yaml"
    fake_config_path.write_text("model: openai/gpt-4o\n")
    monkeypatch.setattr(cli_mod, "DEFAULT_CONFIG_PATH", fake_config_path)

    with (
        patch("notes_gen.cli.subprocess.run"),
        patch("notes_gen.cli.platform.system", return_value="Linux"),
    ):
        runner.invoke(app, ["config", "open"])

    assert fake_config_path.read_text() == "model: openai/gpt-4o\n"


def test_subcommand_help_still_works():
    result = runner.invoke(app, ["video", "--help"])
    assert result.exit_code == 0
    assert "url" in result.output.lower()
