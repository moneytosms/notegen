from __future__ import annotations

from collections import deque
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
import typer
from bs4 import BeautifulSoup

from notes_gen.config import Config
from notes_gen.output.formats import format_notes
from notes_gen.output.formatter import build_frontmatter, slugify
from notes_gen.output.writer import write_index, write_note
from notes_gen.processing.chunker import chunk_text
from notes_gen.processing.filter import remove_meta
from notes_gen.processing.llm import compress_notes, generate_notes
from notes_gen.processing.merger import merge

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_page(url: str) -> str:
    response = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text


async def _fetch_page_async(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.text


def extract_content(html: str, url: str) -> str:
    if not html:
        return ""
    result = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    if result and len(result.strip()) > 100:
        return result.strip()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find("body")
    return main.get_text(separator="\n", strip=True) if main else ""


def _get_title(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"]
    title_tag = soup.find("title")
    if title_tag and title_tag.text:
        return title_tag.text.strip()
    return urlparse(url).path.strip("/").replace("/", "-") or "web-page"


def _same_domain_links(html: str, base_url: str) -> list[str]:
    base_domain = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
            clean = parsed._replace(fragment="").geturl()
            links.append(clean)
    return list(set(links))


def _is_quality_page(content: str) -> bool:
    if len(content) < 500:
        return False
    words = content.split()
    if len(words) < 200:
        return False
    paragraphs = len([p for p in content.split("\n\n") if p.strip()])
    list_items = sum(
        1
        for line in content.splitlines()
        if line.lstrip().startswith(("- ", "* "))
        or (len(line) > 2 and line[0].isdigit() and line[1] in ".)")
    )
    if list_items == 0:
        return True
    return paragraphs / (paragraphs + list_items) > 0.3


def run_web_pipeline(url: str, cfg: Config) -> Path:
    from notes_gen.cache import get_notes_cache, set_notes_cache

    html = fetch_page(url)
    content = extract_content(html, url)
    title = _get_title(html, url)

    filtered = remove_meta(content)
    chunks = chunk_text(filtered, max_tokens=12000, overlap=200)

    if cfg.dry_run:
        from notes_gen.processing.dry_run import print_dry_run_summary

        print_dry_run_summary(title, url, chunks, cfg.model)
        raise typer.Exit(0)

    if cfg.cache:
        cached_notes = get_notes_cache(url, cfg.model)
    else:
        cached_notes = None

    if cached_notes is not None:
        if cfg.verbose:
            typer.echo(f"Using cached notes for {url}", err=True)
        notes_raw, tags = cached_notes, []
    else:
        notes_raw, tags = generate_notes(chunks, cfg)
        if cfg.cache:
            set_notes_cache(url, cfg.model, notes_raw)

    notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
    if cfg.max_output_tokens > 0:
        notes = compress_notes(notes, cfg.max_output_tokens, cfg)
    notes = format_notes(notes, cfg.output_format)
    frontmatter = build_frontmatter(
        title=title,
        source=url,
        type="article",
        tags=tags,
        date=date.today(),
    )
    full_content = frontmatter + "\n" + notes
    slug = slugify(title) or "web-notes"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = cfg.output_dir / f"{slug}.md"
    return write_note(output_path, full_content, overwrite_policy="rename")


def run_web_crawl_pipeline(url: str, cfg: Config) -> Path:
    import anyio

    return anyio.run(_crawl_async, url, cfg)


async def _crawl_async(url: str, cfg: Config) -> Path:
    from rich.progress import Progress

    visited: set[str] = set()
    queue: deque[str] = deque([url])
    page_data: list[tuple[str, str, str]] = []
    depth_map: dict[str, int] = {url: 0}

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        with Progress(transient=True) as progress:
            task = progress.add_task(f"Crawling {urlparse(url).netloc}...", total=cfg.web_max_pages)
            while queue and len(visited) < cfg.web_max_pages:
                current_url = queue.popleft()
                if current_url in visited:
                    continue
                current_depth = depth_map.get(current_url, 0)
                if current_depth > cfg.web_max_depth:
                    continue
                visited.add(current_url)
                progress.advance(task)
                path_label = urlparse(current_url).path[:40] or "/"
                progress.update(
                    task, description=f"[{len(visited)}/{cfg.web_max_pages}] {path_label}"
                )

                try:
                    html = await _fetch_page_async(client, current_url)
                except (httpx.HTTPError, httpx.TimeoutException):
                    continue

                content = extract_content(html, current_url)
                title = _get_title(html, current_url)
                if content and _is_quality_page(content):
                    page_data.append((current_url, title, content))
                elif content and cfg.verbose:
                    typer.echo(f"Skipping low-quality page: {current_url}", err=True)

                if current_depth < cfg.web_max_depth:
                    for link in _same_domain_links(html, current_url):
                        if link not in visited and link not in queue:
                            depth_map[link] = current_depth + 1
                            queue.append(link)

    if not page_data:
        typer.echo("ERROR: No content could be fetched from the provided URL.", err=True)
        raise typer.Exit(1)

    if cfg.dry_run:
        from notes_gen.processing.dry_run import print_dry_run_multi_summary

        entries = []
        for page_url, page_title, content in page_data:
            filtered = remove_meta(content)
            chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
            entries.append((page_title, page_url, chunks))
        print_dry_run_multi_summary(entries, cfg.model)
        raise typer.Exit(0)

    if len(page_data) == 1:
        page_url, title, content = page_data[0]
        filtered = remove_meta(content)
        chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
        notes_raw, tags = generate_notes(chunks, cfg)
        notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
        if cfg.max_output_tokens > 0:
            notes = compress_notes(notes, cfg.max_output_tokens, cfg)
        notes = format_notes(notes, cfg.output_format)
        frontmatter = build_frontmatter(
            title=title, source=page_url, type="article", tags=tags, date=date.today()
        )
        slug = slugify(title) or "web-notes"
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = cfg.output_dir / f"{slug}.md"
        return write_note(output_path, frontmatter + "\n" + notes, overwrite_policy="rename")

    site_slug = slugify(urlparse(url).netloc) or "site"
    site_dir = cfg.output_dir / site_slug
    site_dir.mkdir(parents=True, exist_ok=True)
    page_slugs: list[str] = []

    for page_url, title, content in page_data:
        filtered = remove_meta(content)
        chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
        notes_raw, tags = generate_notes(chunks, cfg)
        notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
        if cfg.max_output_tokens > 0:
            notes = compress_notes(notes, cfg.max_output_tokens, cfg)
        notes = format_notes(notes, cfg.output_format)
        frontmatter = build_frontmatter(
            title=title, source=page_url, type="article", tags=tags, date=date.today()
        )
        slug = slugify(title) or "page"
        page_slugs.append(slug)
        note_path = site_dir / f"{slug}.md"
        write_note(note_path, frontmatter + "\n" + notes, overwrite_policy="rename")

    write_index(site_dir, page_slugs)
    return site_dir / "index.md"
