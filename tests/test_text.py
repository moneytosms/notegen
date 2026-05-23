import io
from pathlib import Path
from unittest.mock import patch

import pytest

from notes_gen.config import Config
from notes_gen.sources.text import read_text

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_transcript.txt"


def test_read_text_from_file():
    content = read_text(str(FIXTURE_PATH))
    assert "asyncio" in content
    assert len(content) > 50


def test_read_text_from_stdin(monkeypatch):
    fake_input = "Hello from stdin\nSecond line"
    monkeypatch.setattr("sys.stdin", io.StringIO(fake_input))
    content = read_text("-")
    assert "Hello from stdin" in content
    assert "Second line" in content


def test_read_text_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_text("/nonexistent/path/file.txt")


def test_read_text_normalizes_whitespace():
    content = read_text(str(FIXTURE_PATH))
    assert "\t\t" not in content
    assert "  " not in content or content.count("  ") < 5  # minimal double-spaces


def test_text_pipeline_end_to_end(tmp_path):
    from notes_gen.sources.text import run_text_pipeline

    cfg = Config(output_dir=tmp_path, model="anthropic/claude-sonnet-4-6")
    notes_content = "## Asyncio\n\nEvent loop drives everything."

    with patch("notes_gen.sources.text.generate_notes", return_value=notes_content):
        output_path = run_text_pipeline(str(FIXTURE_PATH), cfg)

    assert output_path.exists()
    content = output_path.read_text()
    assert "---" in content  # frontmatter
    assert "asyncio" in content.lower() or "Asyncio" in content


def test_text_pipeline_stdin(tmp_path):
    import io

    from notes_gen.sources.text import run_text_pipeline

    cfg = Config(output_dir=tmp_path)
    notes_content = "## Overview\n\nContent from stdin."

    with (
        patch("notes_gen.sources.text.generate_notes", return_value=notes_content),
        patch("sys.stdin", io.StringIO("Test content for stdin pipeline")),
    ):
        output_path = run_text_pipeline("-", cfg)

    assert output_path.exists()


def test_text_pipeline_output_has_frontmatter(tmp_path):
    import yaml

    from notes_gen.sources.text import run_text_pipeline

    cfg = Config(output_dir=tmp_path)
    notes_content = "## Section\n\nSome notes."

    with patch("notes_gen.sources.text.generate_notes", return_value=notes_content):
        output_path = run_text_pipeline(str(FIXTURE_PATH), cfg)

    raw = output_path.read_text()
    assert raw.startswith("---\n")
    parts = raw.split("---\n", 2)
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert "title" in fm
    assert fm["type"] == "article"
