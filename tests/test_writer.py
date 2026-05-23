from notes_gen.output.writer import write_index, write_note


def test_write_note_creates_file(tmp_path):
    target = tmp_path / "test-note.md"
    write_note(target, "# Test\n\nContent.")
    assert target.exists()
    assert target.read_text() == "# Test\n\nContent."


def test_write_note_creates_parent_dirs(tmp_path):
    target = tmp_path / "subdir" / "nested" / "note.md"
    write_note(target, "content")
    assert target.exists()


def test_write_note_overwrite_policy_overwrite(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("old content")
    write_note(target, "new content", overwrite_policy="overwrite")
    assert target.read_text() == "new content"


def test_write_note_overwrite_policy_skip(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("original")
    write_note(target, "new content", overwrite_policy="skip")
    assert target.read_text() == "original"


def test_write_note_overwrite_policy_rename(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("original")
    result_path = write_note(target, "new content", overwrite_policy="rename")
    assert result_path != target
    assert result_path.exists()
    assert result_path.read_text() == "new content"
    assert target.read_text() == "original"


def test_write_note_returns_path(tmp_path):
    target = tmp_path / "note.md"
    result = write_note(target, "content")
    assert result == target


def test_write_index_basic(tmp_path):
    playlist_dir = tmp_path / "my-playlist"
    playlist_dir.mkdir()
    slugs = ["video-one", "video-two", "video-three"]
    write_index(playlist_dir, slugs)
    index = playlist_dir / "index.md"
    assert index.exists()
    content = index.read_text()
    assert "[[video-one]]" in content
    assert "[[video-two]]" in content
    assert "[[video-three]]" in content


def test_write_index_empty_playlist(tmp_path):
    playlist_dir = tmp_path / "empty-playlist"
    playlist_dir.mkdir()
    write_index(playlist_dir, [])
    index = playlist_dir / "index.md"
    assert index.exists()


def test_write_index_title_from_dir_name(tmp_path):
    playlist_dir = tmp_path / "awesome-python-course"
    playlist_dir.mkdir()
    write_index(playlist_dir, ["lesson-1"])
    content = (playlist_dir / "index.md").read_text()
    assert "awesome-python-course" in content.lower() or "Awesome Python Course" in content
