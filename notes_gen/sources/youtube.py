from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import typer
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from yt_dlp import YoutubeDL

from notes_gen.config import Config
from notes_gen.output.formats import format_notes
from notes_gen.output.formatter import build_frontmatter, slugify
from notes_gen.output.writer import write_index, write_note
from notes_gen.processing.chunker import chunk_text
from notes_gen.processing.filter import remove_meta
from notes_gen.processing.llm import compress_notes, generate_notes
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


def _transcript_to_text(transcript_list) -> str:
    def text_of(item) -> str:
        if isinstance(item, dict):
            return item["text"]
        return item.text

    return " ".join(text_of(item) for item in transcript_list)


def _fetch_transcript(video_id: str) -> str:
    api = YouTubeTranscriptApi()
    transcript_list = api.fetch(video_id)
    return _transcript_to_text(transcript_list)


def _video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


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

    try:
        transcript = _fetch_transcript(meta.video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        typer.echo(f'ERROR: No captions for "{meta.title}" ({meta.url})', err=True)
        raise SystemExit(1)

    return meta, transcript


def run_video_pipeline(url: str, cfg: Config) -> Path:
    from notes_gen.cache import (
        get_notes_cache,
        get_transcript_cache,
        set_notes_cache,
        set_transcript_cache,
    )

    meta, transcript = fetch_video(url)
    canonical = _video_url(meta.video_id)

    if cfg.cache:
        cached_transcript = get_transcript_cache(canonical)
        if cached_transcript is not None:
            if cfg.verbose:
                typer.echo(f"Using cached transcript for {canonical}", err=True)
            transcript = cached_transcript
        else:
            set_transcript_cache(canonical, transcript)

    filtered = remove_meta(transcript)
    chunks = chunk_text(filtered, max_tokens=12000, overlap=200)

    if cfg.dry_run:
        from notes_gen.processing.dry_run import print_dry_run_summary

        print_dry_run_summary(meta.title, canonical, chunks, cfg.model)
        raise SystemExit(0)

    if cfg.cache:
        cached_notes = get_notes_cache(canonical, cfg.model)
    else:
        cached_notes = None

    if cached_notes is not None:
        if cfg.verbose:
            typer.echo(f"Using cached notes for {canonical}", err=True)
        notes_raw, tags = cached_notes, []
    else:
        notes_raw, tags = generate_notes(chunks, cfg)
        if cfg.cache:
            set_notes_cache(canonical, cfg.model, notes_raw)

    notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
    if cfg.max_output_tokens > 0:
        notes = compress_notes(notes, cfg.max_output_tokens, cfg)
    notes = format_notes(notes, cfg.output_format)
    frontmatter = build_frontmatter(
        title=meta.title,
        source=meta.url,
        type="video",
        tags=tags,
        date=date.today(),
    )
    content = frontmatter + "\n" + notes
    slug = slugify(meta.title) or "video-notes"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = cfg.output_dir / f"{slug}.md"
    return write_note(output_path, content, overwrite_policy="rename")


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
        video_id = entry.get("id", "")
        url = f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get("url", "")
        videos.append(
            VideoMetadata(
                title=entry.get("title", "Unknown"),
                channel=entry.get("uploader", info.get("uploader", "Unknown")),
                url=url,
                video_id=video_id,
            )
        )
    return playlist_title, videos


def run_playlist_pipeline(
    url: str, cfg: Config, force: bool = False, force_restart: bool = False
) -> Path:
    import anyio

    return anyio.run(_run_playlist_async, url, cfg, force, force_restart)


def _load_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        import json

        try:
            return json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            return {"completed": [], "failed": []}
    return {"completed": [], "failed": []}


def _save_progress(progress_file: Path, state: dict) -> None:
    import json

    progress_file.write_text(json.dumps(state), encoding="utf-8")


async def _run_playlist_async(
    url: str, cfg: Config, force: bool, force_restart: bool
) -> Path:
    import anyio
    from rich.progress import Progress

    playlist_title, videos = fetch_playlist(url)
    playlist_slug = slugify(playlist_title) or "playlist"
    playlist_dir = cfg.output_dir / playlist_slug
    playlist_dir.mkdir(parents=True, exist_ok=True)

    progress_file = playlist_dir / ".progress.json"
    progress_state = {"completed": [], "failed": []}
    if not force_restart:
        progress_state = _load_progress(progress_file)

    video_slugs: list[str] = []
    limiter = anyio.CapacityLimiter(cfg.max_concurrent)

    done_count = [0]
    total_videos = len(videos)
    with Progress() as progress:
        task = progress.add_task(f"[0/{total_videos}] Starting...", total=total_videos)
        results: list[tuple[int, str | None]] = []

        async def _process(idx: int, meta: VideoMetadata) -> None:
            async with limiter:
                slug_candidate = slugify(meta.title) or f"video-{meta.video_id}"
                if slug_candidate in progress_state["completed"]:
                    if cfg.verbose:
                        typer.echo(f"Skipping {meta.title!r} (already completed)", err=True)
                    results.append((idx, slug_candidate))
                    done_count[0] += 1
                    progress.update(task, description=f"[{done_count[0]}/{total_videos}] {meta.title[:40]}")
                    progress.advance(task)
                    return

                try:
                    transcript = await anyio.to_thread.run_sync(
                        lambda: _fetch_transcript(meta.video_id)
                    )
                except (TranscriptsDisabled, NoTranscriptFound):
                    msg = f'ERROR: No captions for "{meta.title}" ({meta.url})'
                    typer.echo(msg, err=True)
                    if slug_candidate not in progress_state["failed"]:
                        progress_state["failed"].append(slug_candidate)
                    _save_progress(progress_file, progress_state)
                    if not force:
                        raise SystemExit(1)
                    done_count[0] += 1
                    progress.update(task, description=f"[{done_count[0]}/{total_videos}] {meta.title[:40]} (skipped)")
                    progress.advance(task)
                    return

                filtered = remove_meta(transcript)
                chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
                notes_raw, tags = await anyio.to_thread.run_sync(
                    lambda: generate_notes(chunks, cfg, max_chunk_workers=1)
                )
                notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
                notes = format_notes(notes, cfg.output_format)
                frontmatter = build_frontmatter(
                    title=meta.title,
                    source=meta.url,
                    type="video",
                    tags=tags,
                    date=date.today(),
                )
                content = frontmatter + "\n" + notes
                slug = slugify(meta.title) or f"video-{meta.video_id}"
                results.append((idx, slug))
                note_path = playlist_dir / f"{slug}.md"
                write_note(note_path, content, overwrite_policy="rename")
                if slug not in progress_state["completed"]:
                    progress_state["completed"].append(slug)
                _save_progress(progress_file, progress_state)
                done_count[0] += 1
                progress.update(task, description=f"[{done_count[0]}/{total_videos}] {meta.title[:40]}")
                progress.advance(task)

        async with anyio.create_task_group() as tg:
            for i, meta in enumerate(videos):
                tg.start_soon(_process, i, meta)

    # preserve original video order for index
    results.sort(key=lambda x: x[0])
    video_slugs = [slug for _, slug in results if slug]
    write_index(playlist_dir, video_slugs)
    if progress_file.exists():
        progress_file.unlink()
    return playlist_dir / "index.md"
