from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import typer
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from yt_dlp import YoutubeDL

from notes_gen.config import Config
from notes_gen.output.formatter import build_frontmatter, slugify
from notes_gen.output.writer import write_index, write_note
from notes_gen.processing.chunker import chunk_text
from notes_gen.processing.filter import remove_meta
from notes_gen.processing.llm import generate_notes
from notes_gen.processing.merger import merge


@dataclass
class VideoMetadata:
    title: str
    channel: str
    url: str
    video_id: str


def _extract_video_id(url: str) -> str:
    import re

    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return url


def _transcript_to_text(transcript_list: list[dict]) -> str:
    return " ".join(item["text"] for item in transcript_list)


def fetch_video(url: str) -> tuple[VideoMetadata, str]:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    meta = VideoMetadata(
        title=info.get("title", "Unknown"),
        channel=info.get("uploader", "Unknown"),
        url=info.get("webpage_url", url),
        video_id=info.get("id", _extract_video_id(url)),
    )

    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.fetch(meta.video_id)
        transcript = _transcript_to_text(transcript_list)
    except (TranscriptsDisabled, NoTranscriptFound):
        typer.echo(f'ERROR: No captions for "{meta.title}" ({meta.url})', err=True)
        raise SystemExit(1)

    return meta, transcript


def run_video_pipeline(url: str, cfg: Config) -> Path:
    meta, transcript = fetch_video(url)
    filtered = remove_meta(transcript)
    chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
    notes_raw = generate_notes(chunks, cfg)
    notes = merge([notes_raw])

    frontmatter = build_frontmatter(
        title=meta.title,
        source=meta.url,
        type="video",
        tags=[],
        date=date.today(),
    )
    content = frontmatter + "\n" + notes
    slug = slugify(meta.title) or "video-notes"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = cfg.output_dir / f"{slug}.md"
    return write_note(output_path, content)


def fetch_playlist(url: str) -> tuple[str, list[VideoMetadata]]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    playlist_title = info.get("title", "playlist")
    entries = info.get("entries", []) or []
    videos = []
    for entry in entries:
        if not entry:
            continue
        videos.append(
            VideoMetadata(
                title=entry.get("title", "Unknown"),
                channel=entry.get("uploader", info.get("uploader", "Unknown")),
                url=entry.get("url", entry.get("webpage_url", "")),
                video_id=entry.get("id", ""),
            )
        )
    return playlist_title, videos


def run_playlist_pipeline(url: str, cfg: Config, force: bool = False) -> Path:
    from rich.progress import Progress

    playlist_title, videos = fetch_playlist(url)
    playlist_slug = slugify(playlist_title) or "playlist"
    playlist_dir = cfg.output_dir / playlist_slug
    playlist_dir.mkdir(parents=True, exist_ok=True)

    video_slugs: list[str] = []

    with Progress() as progress:
        task = progress.add_task(f"Processing {len(videos)} videos...", total=len(videos))
        for meta in videos:
            progress.advance(task)
            try:
                api = YouTubeTranscriptApi()
                transcript_list = api.fetch(meta.video_id)
                transcript = _transcript_to_text(transcript_list)
            except (TranscriptsDisabled, NoTranscriptFound):
                msg = f'ERROR: No captions for "{meta.title}" ({meta.url})'
                typer.echo(msg, err=True)
                if not force:
                    raise SystemExit(1)
                continue

            filtered = remove_meta(transcript)
            chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
            notes_raw = generate_notes(chunks, cfg)
            notes = merge([notes_raw])

            frontmatter = build_frontmatter(
                title=meta.title,
                source=meta.url,
                type="video",
                tags=[],
                date=date.today(),
            )
            content = frontmatter + "\n" + notes
            slug = slugify(meta.title) or f"video-{meta.video_id}"
            video_slugs.append(slug)
            note_path = playlist_dir / f"{slug}.md"
            write_note(note_path, content)

    write_index(playlist_dir, video_slugs)
    return playlist_dir / "index.md"
