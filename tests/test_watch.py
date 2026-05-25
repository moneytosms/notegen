from unittest.mock import patch


def test_watch_state_load_save(tmp_path):
    from notes_gen.sources.watch import _load_state, _save_state

    assert _load_state(tmp_path) == set()

    _save_state(tmp_path, {"file_a.txt", "file_b.txt"})
    loaded = _load_state(tmp_path)
    assert "file_a.txt" in loaded
    assert "file_b.txt" in loaded


def test_watch_state_corrupted_returns_empty(tmp_path):
    from notes_gen.sources.watch import _load_state

    (tmp_path / ".watch-state.json").write_text("NOT JSON", encoding="utf-8")
    assert _load_state(tmp_path) == set()


def test_watch_processes_existing_files(tmp_path):
    from notes_gen.config import Config
    from notes_gen.sources.watch import run_watch

    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Some content here for testing.", encoding="utf-8")
    out_path = tmp_path / "notes.md"

    def fake_watch(directory, watch_filter=None):
        return iter([])

    with (
        patch("notes_gen.sources.watch.watch", return_value=iter([])),
        patch("notes_gen.sources.watch._process_file", return_value=True) as mock_process,
    ):
        import typer

        try:
            run_watch(tmp_path, Config(output_dir=tmp_path, cache=False))
        except (SystemExit, typer.Exit):
            pass

    assert mock_process.call_count >= 1
    call_args = mock_process.call_args_list[0][0]
    assert call_args[0] == txt_file


def test_watch_skips_already_processed(tmp_path):
    from notes_gen.config import Config
    from notes_gen.sources.watch import _save_state, run_watch

    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("content", encoding="utf-8")
    _save_state(tmp_path, {str(txt_file)})

    def fake_watch(directory, watch_filter=None):
        return iter([])

    with (
        patch("notes_gen.sources.watch.watch", return_value=iter([])),
        patch("notes_gen.sources.watch._process_file", return_value=True) as mock_process,
    ):
        import typer

        try:
            run_watch(tmp_path, Config(output_dir=tmp_path, cache=False))
        except (SystemExit, typer.Exit):
            pass

    mock_process.assert_not_called()


def test_watch_ignores_non_text_files(tmp_path):
    from notes_gen.sources.watch import _change_filter

    assert _change_filter(None, str(tmp_path / "file.txt"))
    assert _change_filter(None, str(tmp_path / "file.md"))
    assert not _change_filter(None, str(tmp_path / "file.py"))
    assert not _change_filter(None, str(tmp_path / ".watch-state.json"))


def test_watch_command_exists():
    from typer.testing import CliRunner

    from notes_gen.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["watch", "--help"])
    assert result.exit_code == 0
    assert "directory" in result.output.lower() or "watch" in result.output.lower()


def test_process_file_returns_true_on_success(tmp_path):
    from unittest.mock import patch

    from notes_gen.config import Config
    from notes_gen.sources.watch import _process_file

    f = tmp_path / "note.txt"
    f.write_text("content", encoding="utf-8")

    with patch("notes_gen.sources.text.run_text_pipeline", return_value=tmp_path / "note.md"):
        result = _process_file(f, Config(output_dir=tmp_path, cache=False))

    assert result is True


def test_process_file_returns_false_on_error(tmp_path):
    from unittest.mock import patch

    from notes_gen.config import Config
    from notes_gen.sources.watch import _process_file

    f = tmp_path / "note.txt"
    f.write_text("content", encoding="utf-8")

    with patch("notes_gen.sources.text.run_text_pipeline", side_effect=RuntimeError("boom")):
        result = _process_file(f, Config(output_dir=tmp_path, cache=False))

    assert result is False


def test_watch_processes_new_file_events(tmp_path):
    from unittest.mock import patch

    from notes_gen.config import Config
    from notes_gen.sources.watch import run_watch

    txt_file = tmp_path / "new.txt"
    txt_file.write_text("content", encoding="utf-8")

    fake_changes = [[(None, str(txt_file))]]

    with (
        patch("notes_gen.sources.watch.watch", return_value=iter(fake_changes)),
        patch("notes_gen.sources.watch._process_file", return_value=True) as mock_proc,
    ):
        run_watch(tmp_path, Config(output_dir=tmp_path, cache=False))

    assert mock_proc.call_count >= 1
