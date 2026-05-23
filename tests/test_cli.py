from unittest.mock import patch

from typer.testing import CliRunner

from notes_gen.cli import app, main

runner = CliRunner()


def test_help_shows_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "video" in result.output
    assert "playlist" in result.output
    assert "web" in result.output
    assert "text" in result.output


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


def test_text_command_wired(tmp_path):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "sample_transcript.txt"
    with patch("notes_gen.sources.text.generate_notes", return_value="## Notes\n\nContent."):
        result = runner.invoke(app, ["text", str(fixture), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Notes written to" in result.output
