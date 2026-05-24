from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from notes_gen.config import Config
from notes_gen.sources.youtube import (
    VideoMetadata,
    fetch_playlist,
    fetch_video,
    run_playlist_pipeline,
    run_video_pipeline,
)


def _make_transcript_list():
    return [
        {"text": "Welcome to this Python tutorial.", "start": 0.0, "duration": 3.0},
        {"text": "Today we will cover asyncio.", "start": 3.0, "duration": 3.0},
        {"text": "The event loop is the core.", "start": 6.0, "duration": 3.0},
    ]


def _make_object_transcript_list():
    return [
        SimpleNamespace(text="Welcome to this Python tutorial.", start=0.0, duration=3.0),
        SimpleNamespace(text="Today we will cover asyncio.", start=3.0, duration=3.0),
        SimpleNamespace(text="The event loop is the core.", start=6.0, duration=3.0),
    ]


def _make_yt_info():
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Python Asyncio Tutorial",
        "uploader": "PyChannel",
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_fetch_video_returns_metadata_and_transcript(mock_yt_api, mock_ytdl):
    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_yt_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.return_value = _make_transcript_list()

    meta, transcript = fetch_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert isinstance(meta, VideoMetadata)
    assert meta.title == "Python Asyncio Tutorial"
    assert meta.channel == "PyChannel"
    assert "asyncio" in transcript.lower()


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_fetch_video_accepts_object_transcript_snippets(mock_yt_api, mock_ytdl):
    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_yt_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.return_value = _make_object_transcript_list()

    _, transcript = fetch_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert "asyncio" in transcript.lower()


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_fetch_video_no_captions_raises(mock_yt_api, mock_ytdl):
    from youtube_transcript_api._errors import TranscriptsDisabled

    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_yt_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")

    with pytest.raises(SystemExit) as exc_info:
        fetch_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert exc_info.value.code != 0


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_run_video_pipeline_creates_file(mock_yt_api, mock_ytdl, tmp_path):
    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_yt_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.return_value = _make_transcript_list()

    cfg = Config(output_dir=tmp_path, cache=False)
    notes_content = "## Asyncio\n\nEvent loop is the core."

    with patch("notes_gen.sources.youtube.generate_notes", return_value=(notes_content, [])):
        output_path = run_video_pipeline("https://www.youtube.com/watch?v=dQw4w9WgXcQ", cfg)

    assert output_path.exists()
    content = output_path.read_text()
    assert "type: video" in content
    assert "---" in content


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_run_video_pipeline_slug_filename(mock_yt_api, mock_ytdl, tmp_path):
    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_yt_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.return_value = _make_transcript_list()

    cfg = Config(output_dir=tmp_path, cache=False)

    with patch(
        "notes_gen.sources.youtube.generate_notes", return_value=("## Notes\n\nContent.", [])
    ):
        output_path = run_video_pipeline("https://www.youtube.com/watch?v=dQw4w9WgXcQ", cfg)

    assert output_path.name == "python-asyncio-tutorial.md"


def test_video_metadata_dataclass():
    meta = VideoMetadata(
        title="Test Video",
        channel="Test Channel",
        url="https://youtube.com/watch?v=test",
        video_id="test",
    )
    assert meta.title == "Test Video"


# --- Playlist tests ---


def _make_playlist_info():
    return {
        "title": "Python Tutorial Series",
        "uploader": "PyChannel",
        "entries": [
            {
                "id": "vid001",
                "title": "Intro to Python",
                "uploader": "PyChannel",
                "url": "https://youtube.com/watch?v=vid001",
                "webpage_url": "https://youtube.com/watch?v=vid001",
            },
            {
                "id": "vid002",
                "title": "Python Functions",
                "uploader": "PyChannel",
                "url": "https://youtube.com/watch?v=vid002",
                "webpage_url": "https://youtube.com/watch?v=vid002",
            },
        ],
    }


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_run_playlist_pipeline_creates_index(mock_yt_api, mock_ytdl, tmp_path):
    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_playlist_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.return_value = _make_transcript_list()

    cfg = Config(output_dir=tmp_path, cache=False)

    with patch(
        "notes_gen.sources.youtube.generate_notes", return_value=("## Notes\n\nContent.", [])
    ):
        index_path = run_playlist_pipeline("https://youtube.com/playlist?list=PL123", cfg)

    assert index_path.exists()
    assert index_path.name == "index.md"
    content = index_path.read_text()
    assert "[[" in content


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_run_playlist_pipeline_skips_on_force(mock_yt_api, mock_ytdl, tmp_path):
    from youtube_transcript_api._errors import TranscriptsDisabled

    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_playlist_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.side_effect = TranscriptsDisabled("vid001")

    cfg = Config(output_dir=tmp_path, cache=False)

    # With force=True, no-caption videos are skipped, pipeline continues
    with patch(
        "notes_gen.sources.youtube.generate_notes", return_value=("## Notes\n\nContent.", [])
    ):
        index_path = run_playlist_pipeline(
            "https://youtube.com/playlist?list=PL123", cfg, force=True
        )

    assert index_path.exists()


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_run_playlist_pipeline_aborts_without_force(mock_yt_api, mock_ytdl, tmp_path):
    from youtube_transcript_api._errors import TranscriptsDisabled

    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_playlist_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.side_effect = TranscriptsDisabled("vid001")

    cfg = Config(output_dir=tmp_path, cache=False)

    with pytest.raises(SystemExit) as exc_info:
        with patch("notes_gen.sources.youtube.generate_notes", return_value=("notes", [])):
            run_playlist_pipeline("https://youtube.com/playlist?list=PL123", cfg, force=False)

    assert exc_info.value.code != 0


@patch("notes_gen.sources.youtube.YoutubeDL")
@patch("notes_gen.sources.youtube.YouTubeTranscriptApi")
def test_playlist_resume_skips_completed(mock_yt_api, mock_ytdl, tmp_path):
    """Videos listed in .progress.json completed are skipped (no transcript fetch)."""
    import json

    mock_ytdl.return_value.__enter__ = MagicMock(
        return_value=MagicMock(extract_info=MagicMock(return_value=_make_playlist_info()))
    )
    mock_ytdl.return_value.__exit__ = MagicMock(return_value=False)
    mock_yt_api.return_value.fetch.return_value = _make_transcript_list()

    cfg = Config(output_dir=tmp_path, cache=False)
    # slug of "Python Tutorial Series" (the playlist title from _make_playlist_info)
    playlist_dir = tmp_path / "python-tutorial-series"
    playlist_dir.mkdir()

    # pre-write progress with first video already done
    # slug of "Intro to Python" (first video title)
    first_slug = "intro-to-python"
    progress_file = playlist_dir / ".progress.json"
    progress_file.write_text(json.dumps({"completed": [first_slug], "failed": []}))
    (playlist_dir / f"{first_slug}.md").write_text("pre-existing note")

    call_count = 0

    def counting_fetch(video_id):
        nonlocal call_count
        call_count += 1
        return _make_transcript_list()

    mock_yt_api.return_value.fetch.side_effect = counting_fetch

    with patch(
        "notes_gen.sources.youtube.generate_notes", return_value=("## Notes\n\nContent.", [])
    ):
        run_playlist_pipeline("https://youtube.com/playlist?list=PL123", cfg)

    # only 1 transcript fetch (second video); first was skipped
    assert call_count == 1
    assert not progress_file.exists()  # deleted on full success


def test_fetch_playlist_video_urls_are_full_youtube_urls():
    entries = [{"id": "abc123", "title": "Test Video", "uploader": "Channel"}]
    info = {"title": "My Playlist", "uploader": "Channel", "entries": entries}

    with patch("notes_gen.sources.youtube.YoutubeDL") as mock_ydl:
        mock_ydl.return_value.__enter__.return_value.extract_info.return_value = info
        _, videos = fetch_playlist("https://youtube.com/playlist?list=PL123")

    assert videos[0].url == "https://www.youtube.com/watch?v=abc123"
    assert videos[0].video_id == "abc123"
