from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional, cast

import typer
from loguru import logger
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
    duration: int = 0
    chapters: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""


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


_TRANSLATABLE_LANGS = ["hi", "ml"]


def _fetch_transcript(video_id: str, lang: str = "en") -> str:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)  # raises TranscriptsDisabled if no captions at all

    # 1. Try to find the transcript in the requested language
    try:
        t = transcript_list.find_transcript([lang])
        return _transcript_to_text(t.fetch())
    except NoTranscriptFound:
        pass

    # 2. Try to translate any available transcript to the requested language
    try:
        available_langs = [t.language_code for t in transcript_list]
        t = transcript_list.find_transcript(available_langs).translate(lang)
        return _transcript_to_text(t.fetch())
    except Exception:
        pass

    # 3. Last resort: English
    try:
        t = transcript_list.find_transcript(["en", "en-US", "en-GB"])
        return _transcript_to_text(t.fetch())
    except NoTranscriptFound:
        t = next(iter(transcript_list))
        return _transcript_to_text(t.translate(lang).fetch())


def _video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _format_chapters(chapters: list[dict[str, Any]]) -> str:
    if not chapters:
        return ""
    lines = ["Video Chapters:"]
    for c in chapters:
        start = c.get("start_time", 0)
        title = c.get("title", "Untitled")
        minutes = int(start // 60)
        seconds = int(start % 60)
        lines.append(f"- {minutes:02d}:{seconds:02d} {title}")
    return "\n".join(lines)


def fetch_video(url: str, lang: str = "en") -> tuple[VideoMetadata, str]:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with YoutubeDL(ydl_opts) as ydl:  # type: ignore
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("Could not fetch video info")

    meta = VideoMetadata(
        title=cast(str, info.get("title", "Unknown")),
        channel=cast(str, info.get("uploader", "Unknown")),
        url=cast(str, info.get("webpage_url", url)),
        video_id=cast(str, info.get("id", _extract_video_id(url))),
        duration=int(info.get("duration") or 0),
        chapters=info.get("chapters", []) or [],
        description=cast(str, info.get("description", "")),
    )

    try:
        transcript = _fetch_transcript(meta.video_id, lang=lang)
    except (TranscriptsDisabled, NoTranscriptFound):
        logger.error(f'No captions for "{meta.title}" ({meta.url})')
        raise SystemExit(1)

    return meta, transcript


def run_video_pipeline(url: str, cfg: Config) -> Path:
    from notes_gen.cache import (
        get_notes_cache,
        get_transcript_cache,
        set_notes_cache,
        set_transcript_cache,
    )
    from notes_gen.output.runner import use_dashboard, log_to_dashboard, update_dashboard_stats
    from notes_gen.processing.chunker import count_tokens
    from notes_gen.processing.dry_run import _cost_str
    from notes_gen.processing.filter import remove_meta

    with use_dashboard("YouTube Video", cfg) as db:
        log_to_dashboard(f"Fetching metadata for {url}...")
        meta, transcript = fetch_video(url, lang=cfg.language)
        if db:
            db.title = f"Video: {meta.title[:50]}"
            db._init_layout()

        canonical = _video_url(meta.video_id)

        if cfg.cache:
            cached_transcript = get_transcript_cache(canonical)
            if cached_transcript is not None:
                log_to_dashboard("Using cached transcript")
                transcript = cached_transcript
            else:
                set_transcript_cache(canonical, transcript)

        log_to_dashboard("Filtering transcript...")
        filtered = remove_meta(transcript)
        
        tokens = count_tokens(filtered)
        update_dashboard_stats(tokens, _cost_str(tokens, cfg.model))
        
        # Inject chapters into extra prompt for better context
        original_extra = cfg.extra_prompt
        chapter_context = _format_chapters(meta.chapters)
        if chapter_context:
            cfg.extra_prompt = f"{chapter_context}\n\n{original_extra}".strip()

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
            log_to_dashboard("Using cached notes")
            notes_raw, tags = cached_notes, []
        else:
            log_to_dashboard(f"Generating notes via {cfg.model}...")
            notes_raw, tags = generate_notes(chunks, cfg)
            if cfg.cache:
                set_notes_cache(canonical, cfg.model, notes_raw)

        log_to_dashboard("Merging and formatting...")
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
        result_path = write_note(output_path, content)
        log_to_dashboard(f"[green]Completed:[/] {result_path.name}")
        return result_path


def fetch_playlist(url: str) -> tuple[str, list[VideoMetadata]]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
    }
    with YoutubeDL(ydl_opts) as ydl:  # type: ignore
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("Could not fetch playlist info")

    playlist_title = cast(str, info.get("title", "playlist"))
    entries = info.get("entries", []) or []
    videos = []
    for entry in entries:
        if not entry:
            continue
        video_id = cast(str, entry.get("id", ""))
        v_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else cast(str, entry.get("url", ""))
        videos.append(
            VideoMetadata(
                title=cast(str, entry.get("title", "Unknown")),
                channel=cast(str, entry.get("uploader", info.get("uploader", "Unknown"))),
                url=v_url,
                video_id=video_id,
                duration=int(entry.get("duration") or 0),
                chapters=entry.get("chapters", []) or [],
                description=cast(str, entry.get("description", "")),
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


async def _run_playlist_async(url: str, cfg: Config, force: bool, force_restart: bool) -> Path:
    import anyio
    from notes_gen.output.dashboard import Dashboard
    from notes_gen.processing.dry_run import _cost_str
    from notes_gen.processing.chunker import count_tokens

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
    total_tokens = [0]
    total_videos = len(videos)
    
    with Dashboard(f"Playlist: {playlist_title}", cfg.model) as db:
        db.update_progress(0, total_videos, f"[0/{total_videos}] Initializing...")
        results: list[tuple[int, str | None]] = []

        async def _process(idx: int, meta: VideoMetadata) -> None:
            async with limiter:
                slug_candidate = slugify(meta.title) or f"video-{meta.video_id}"
                note_path = playlist_dir / f"{slug_candidate}.md"

                if cfg.incremental and note_path.exists():
                    db.log(f"Skipping {meta.title[:30]} (file exists)")
                    results.append((idx, slug_candidate))
                    done_count[0] += 1
                    db.update_progress(done_count[0], total_videos, f"[{done_count[0]}/{total_videos}] {meta.title[:40]}")
                    return

                if slug_candidate in progress_state["completed"]:
                    db.log(f"Skipping {meta.title[:30]} (already done)")
                    results.append((idx, slug_candidate))
                    done_count[0] += 1
                    db.update_progress(done_count[0], total_videos, f"[{done_count[0]}/{total_videos}] {meta.title[:40]}")
                    return

                try:
                    db.log(f"Fetching {meta.title[:30]}...")
                    transcript = await cast(Any, anyio.to_thread).run_sync(
                        lambda: _fetch_transcript(meta.video_id, lang=cfg.language)
                    )
                except (TranscriptsDisabled, NoTranscriptFound):
                    db.log(f"[bold red]No captions for {meta.title[:30]}[/]")
                    if slug_candidate not in progress_state["failed"]:
                        progress_state["failed"].append(slug_candidate)
                    _save_progress(progress_file, progress_state)
                    if not force:
                        raise SystemExit(1)
                    done_count[0] += 1
                    db.update_progress(done_count[0], total_videos, f"[{done_count[0]}/{total_videos}] {meta.title[:40]} (skipped)")
                    return

                db.log(f"Generating notes for {meta.title[:30]}...")
                filtered = remove_meta(transcript)
                chunk_tokens = count_tokens(filtered)
                total_tokens[0] += chunk_tokens
                db.update_stats(total_tokens[0], _cost_str(total_tokens[0], cfg.model))
                
                # Inject chapters for this video
                video_extra = cfg.extra_prompt
                chapter_context = _format_chapters(meta.chapters)
                video_cfg = cfg
                if chapter_context:
                    from dataclasses import replace
                    video_cfg = replace(cfg, extra_prompt=f"{chapter_context}\n\n{video_extra}".strip())

                chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
                notes_raw, tags = await cast(Any, anyio.to_thread).run_sync(
                    lambda: generate_notes(chunks, video_cfg, max_chunk_workers=1)
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
                db.log(f"[green]Completed {meta.title[:30]}[/]")
                db.update_progress(done_count[0], total_videos, f"[{done_count[0]}/{total_videos}] {meta.title[:40]}")

        async with anyio.create_task_group() as tg:
            for i, meta in enumerate(videos):
                tg.start_soon(_process, i, meta)

    results.sort(key=lambda x: x[0])
    video_slugs = [slug for _, slug in results if slug]
    write_index(playlist_dir, video_slugs)
    if progress_file.exists():
        progress_file.unlink()
    return playlist_dir / "index.md"
