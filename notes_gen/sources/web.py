from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from notes_gen.config import Config
from notes_gen.output.formatter import build_frontmatter, slugify
from notes_gen.output.writer import write_index, write_note
from notes_gen.processing.chunker import chunk_text
from notes_gen.processing.filter import remove_meta
from notes_gen.processing.llm import generate_notes
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


def run_web_pipeline(url: str, cfg: Config) -> Path:
    html = fetch_page(url)
    content = extract_content(html, url)
    title = _get_title(html, url)

    filtered = remove_meta(content)
    chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
    notes_raw = generate_notes(chunks, cfg)
    notes = merge([notes_raw])

    frontmatter = build_frontmatter(
        title=title,
        source=url,
        type="article",
        tags=[],
        date=date.today(),
    )
    full_content = frontmatter + "\n" + notes
    slug = slugify(title) or "web-notes"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = cfg.output_dir / f"{slug}.md"
    return write_note(output_path, full_content)


def run_web_crawl_pipeline(url: str, cfg: Config) -> Path:
    from rich.progress import Progress

    visited: set[str] = set()
    queue = [url]
    page_data: list[tuple[str, str, str]] = []  # (url, title, content)
    depth_map: dict[str, int] = {url: 0}

    with Progress() as progress:
        task = progress.add_task("Crawling...", total=cfg.web_max_pages)
        while queue and len(visited) < cfg.web_max_pages:
            current_url = queue.pop(0)
            if current_url in visited:
                continue
            current_depth = depth_map.get(current_url, 0)
            if current_depth > cfg.web_max_depth:
                continue
            visited.add(current_url)
            progress.advance(task)

            try:
                html = fetch_page(current_url)
            except Exception:
                continue

            content = extract_content(html, current_url)
            title = _get_title(html, current_url)
            if content:
                page_data.append((current_url, title, content))

            if current_depth < cfg.web_max_depth:
                for link in _same_domain_links(html, current_url):
                    if link not in visited and link not in queue:
                        depth_map[link] = current_depth + 1
                        queue.append(link)

    if len(page_data) == 1:
        page_url, title, content = page_data[0]
        filtered = remove_meta(content)
        chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
        notes_raw = generate_notes(chunks, cfg)
        notes = merge([notes_raw])
        frontmatter = build_frontmatter(
            title=title, source=page_url, type="article", tags=[], date=date.today()
        )
        slug = slugify(title) or "web-notes"
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = cfg.output_dir / f"{slug}.md"
        return write_note(output_path, frontmatter + "\n" + notes)

    site_slug = slugify(urlparse(url).netloc) or "site"
    site_dir = cfg.output_dir / site_slug
    site_dir.mkdir(parents=True, exist_ok=True)
    page_slugs: list[str] = []

    for page_url, title, content in page_data:
        filtered = remove_meta(content)
        chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
        notes_raw = generate_notes(chunks, cfg)
        notes = merge([notes_raw])
        frontmatter = build_frontmatter(
            title=title, source=page_url, type="article", tags=[], date=date.today()
        )
        slug = slugify(title) or "page"
        page_slugs.append(slug)
        note_path = site_dir / f"{slug}.md"
        write_note(note_path, frontmatter + "\n" + notes)

    write_index(site_dir, page_slugs)
    return site_dir / "index.md"
