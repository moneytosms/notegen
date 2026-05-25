from __future__ import annotations

from collections import deque
from datetime import date
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from notes_gen.config import Config
from notes_gen.output.formats import format_notes
from notes_gen.output.formatter import build_frontmatter, generate_toc, slugify
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def fetch_page(url: str) -> str:
    response = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text


async def _fetch_page_async(client: httpx.AsyncClient, url: str) -> str:
    for attempt in range(3):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            if attempt == 2:
                raise
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise
            import asyncio

            await asyncio.sleep(2**attempt)
    raise RuntimeError("unreachable")


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
        return cast(str, og_title["content"])
    title_tag = soup.find("title")
    if title_tag and title_tag.text:
        return title_tag.text.strip()
    return urlparse(url).path.strip("/").replace("/", "-") or "web-page"


def _get_metadata(html: str, url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    meta = {}

    # 1. Author
    author_tags: list[tuple[str, dict[str, str]]] = [
        ("meta", {"name": "author"}),
        ("meta", {"property": "article:author"}),
        ("meta", {"name": "twitter:creator"}),
    ]
    for tag, attrs in author_tags:
        found = soup.find(tag, attrs=cast(Any, attrs))
        if found and found.get("content"):
            meta["author"] = cast(str, found["content"])
            break

    # 2. Date
    date_tags: list[tuple[str, dict[str, str]]] = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "publish-date"}),
    ]
    for tag, attrs in date_tags:
        found = soup.find(tag, attrs=cast(Any, attrs))
        if found and found.get("content"):
            meta["published"] = cast(str, found["content"])[:10]
            break

    # 3. Description
    desc_tags: list[tuple[str, dict[str, str]]] = [
        ("meta", {"name": "description"}),
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "twitter:description"}),
    ]
    for tag, attrs in desc_tags:
        found = soup.find(tag, attrs=cast(Any, attrs))
        if found and found.get("content"):
            meta["description"] = cast(str, found["content"])
            break

    return meta


def _same_domain_links(html: str, base_url: str) -> list[str]:
    base_domain = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = cast(str, a["href"])
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


def _get_images(soup: BeautifulSoup, url: str, cfg: Config, output_dir: Path) -> list[str]:
    if not cfg.download_images:
        return []

    assets_dir = output_dir / "assets"
    images = []

    # Find primary images (e.g. og:image or high-quality img tags)
    og_image = soup.find("meta", property="og:image")
    potential_urls = []
    if og_image and og_image.get("content"):
        potential_urls.append(cast(str, og_image["content"]))

    for img in soup.find_all("img", src=True):
        src = cast(str, img["src"])
        if src.startswith("http"):
            potential_urls.append(src)
        else:
            potential_urls.append(urljoin(url, src))

    # Download top 3 images to avoid bloat
    count = 0
    for img_url in potential_urls[:10]:  # Check top 10
        if count >= 3:
            break
        try:
            ext = Path(urlparse(img_url).path).suffix or ".jpg"
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue

            assets_dir.mkdir(parents=True, exist_ok=True)
            img_name = f"img-{slugify(img_url[:30])}{ext}"
            img_path = assets_dir / img_name

            if not img_path.exists():
                resp = httpx.get(img_url, headers=_HEADERS, timeout=10)
                resp.raise_for_status()
                img_path.write_bytes(resp.content)

            images.append(
                f"![[{img_name}]]"
                if cfg.output_format == "obsidian"
                else f"![Image](assets/{img_name})"
            )
            count += 1
        except Exception as e:
            logger.debug(f"Failed to download image {img_url}: {e}")

    return images


def run_web_pipeline(url: str, cfg: Config) -> Path:
    from notes_gen.cache import get_notes_cache, set_notes_cache
    from notes_gen.output.runner import log_to_dashboard, use_dashboard

    with use_dashboard("Web Article", cfg) as _db:
        log_to_dashboard(f"Fetching {url}...")
        html = fetch_page(url)
        soup = BeautifulSoup(html, "html.parser")
        content = extract_content(html, url)
        title = _get_title(html, url)
        metadata = _get_metadata(html, url)

        # Download images
        log_to_dashboard("Processing images...")
        images_md = _get_images(soup, url, cfg, cfg.output_dir)

        content_with_images = content
        if images_md:
            content_with_images = "\n\n".join(images_md) + "\n\n" + content

        chunks = chunk_text(content_with_images, max_tokens=12000, overlap=200)

        if cfg.dry_run:
            from notes_gen.processing.dry_run import print_dry_run_summary

            print_dry_run_summary(title, url, chunks, cfg.model)
            raise SystemExit(0)

        if cfg.cache:
            cached_notes = get_notes_cache(url, cfg.model)
        else:
            cached_notes = None

        if cached_notes is not None:
            log_to_dashboard("Using cached notes")
            notes_raw, tags = cached_notes, []
        else:
            log_to_dashboard(f"Generating notes via {cfg.model}...")
            notes_raw, tags = generate_notes(chunks, cfg)
            if cfg.cache:
                set_notes_cache(url, cfg.model, notes_raw)

        log_to_dashboard("Merging and formatting...")
        notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
        if cfg.max_output_tokens > 0:
            notes = compress_notes(notes, cfg.max_output_tokens, cfg)
        notes = format_notes(notes, cfg.output_format)
        if cfg.toc:
            notes = generate_toc(notes)
        frontmatter = build_frontmatter(
            title=title,
            source=url,
            type="article",
            tags=tags,
            date=date.today(),
            **metadata,
        )
        full_content = frontmatter + "\n" + notes
        slug = slugify(title) or "web-notes"
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = cfg.output_dir / f"{slug}.md"
        result_path = write_note(output_path, full_content, overwrite_policy="rename")
        log_to_dashboard(f"[green]Completed:[/] {result_path.name}")
        return result_path


def run_web_crawl_pipeline(url: str, cfg: Config) -> Path:
    import anyio

    return anyio.run(_crawl_async, url, cfg)


async def _crawl_async(url: str, cfg: Config) -> Path:
    from notes_gen.output.runner import log_to_dashboard, update_dashboard_stats, use_dashboard
    from notes_gen.processing.chunker import count_tokens
    from notes_gen.processing.dry_run import _cost_str

    with use_dashboard(f"Web Crawl: {urlparse(url).netloc}", cfg) as db:
        visited: set[str] = set()
        queue: deque[str] = deque([url])
        page_data: list[tuple[str, str, str, dict[str, str]]] = []
        depth_map: dict[str, int] = {url: 0}

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
            while queue and len(visited) < cfg.web_max_pages:
                current_url = queue.popleft()
                if current_url in visited:
                    continue
                current_depth = depth_map.get(current_url, 0)
                if current_depth > cfg.web_max_depth:
                    continue
                visited.add(current_url)

                log_to_dashboard(f"Crawling {current_url}...")
                if db:
                    path_label = urlparse(current_url).path[:40] or "/"
                    db.update_progress(
                        len(visited),
                        cfg.web_max_pages,
                        f"[{len(visited)}/{cfg.web_max_pages}] {path_label}",
                    )

                try:
                    html = await _fetch_page_async(client, current_url)
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    log_to_dashboard(f"[bold red]Error fetching {current_url}: {e}[/]")
                    continue

                content = extract_content(html, current_url)
                title = _get_title(html, current_url)
                metadata = _get_metadata(html, current_url)

                # Image handling for crawl
                page_soup = BeautifulSoup(html, "html.parser")
                site_slug = slugify(urlparse(url).netloc) or "site"
                images_md = _get_images(page_soup, current_url, cfg, cfg.output_dir / site_slug)

                if content and _is_quality_page(content):
                    page_content = content
                    if images_md:
                        page_content = "\n\n".join(images_md) + "\n\n" + content
                    page_data.append((current_url, title, page_content, metadata))
                    log_to_dashboard(f"Found quality page: {title[:30]}")
                elif content:
                    log_to_dashboard(f"Skipping low-quality page: {current_url}")

                if current_depth < cfg.web_max_depth:
                    for link in _same_domain_links(html, current_url):
                        if link not in visited and link not in queue:
                            depth_map[link] = current_depth + 1
                            queue.append(link)

        if not page_data:
            log_to_dashboard(
                "[bold red]ERROR: No content could be fetched from the provided URL.[/]"
            )
            raise SystemExit(1)

        if cfg.dry_run:
            from notes_gen.processing.dry_run import print_dry_run_multi_summary

            entries = []
            for page_url, page_title, content, _ in page_data:
                filtered = remove_meta(content)
                chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
                entries.append((page_title, page_url, chunks))
            print_dry_run_multi_summary(entries, cfg.model)
            raise SystemExit(0)

        total_tokens = 0
        all_tags = []

        if len(page_data) == 1:
            page_url, title, content, metadata = page_data[0]
            log_to_dashboard(f"Generating notes for {title[:30]}...")
            filtered = remove_meta(content)

            p_tokens = count_tokens(filtered)
            total_tokens += p_tokens
            update_dashboard_stats(total_tokens, _cost_str(total_tokens, cfg.model))

            chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
            notes_raw, tags = generate_notes(chunks, cfg)
            notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
            if cfg.max_output_tokens > 0:
                notes = compress_notes(notes, cfg.max_output_tokens, cfg)
            notes = format_notes(notes, cfg.output_format)
            if cfg.toc:
                notes = generate_toc(notes)
            frontmatter = build_frontmatter(
                title=title,
                source=page_url,
                type="article",
                tags=tags,
                date=date.today(),
                **metadata,
            )
            slug = slugify(title) or "web-notes"
            cfg.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = cfg.output_dir / f"{slug}.md"
            res = write_note(output_path, frontmatter + "\n" + notes, overwrite_policy="rename")
            log_to_dashboard(f"[green]Completed:[/] {res.name}")
            return res

        site_slug = slugify(urlparse(url).netloc) or "site"
        site_dir = cfg.output_dir / site_slug
        site_dir.mkdir(parents=True, exist_ok=True)
        page_slugs: list[str] = []

        log_to_dashboard(f"Generating notes for {len(page_data)} pages...")
        for page_url, title, content, metadata in page_data:
            log_to_dashboard(f"Processing {title[:30]}...")
            filtered = remove_meta(content)

            p_tokens = count_tokens(filtered)
            total_tokens += p_tokens
            update_dashboard_stats(total_tokens, _cost_str(total_tokens, cfg.model))

            chunks = chunk_text(filtered, max_tokens=12000, overlap=200)
            notes_raw, tags = generate_notes(chunks, cfg)
            notes = merge([notes_raw], similarity_threshold=cfg.merger_similarity_threshold)
            if cfg.max_output_tokens > 0:
                notes = compress_notes(notes, cfg.max_output_tokens, cfg)
            notes = format_notes(notes, cfg.output_format)
            if cfg.toc:
                notes = generate_toc(notes)
            frontmatter = build_frontmatter(
                title=title,
                source=page_url,
                type="article",
                tags=tags,
                date=date.today(),
                **metadata,
            )
            slug = slugify(title) or f"page-{len(page_slugs)}"
            page_slugs.append(slug)
            write_note(
                site_dir / f"{slug}.md", frontmatter + "\n" + notes, overwrite_policy="rename"
            )
            all_tags.extend(t for t in tags if t not in all_tags)

        write_index(site_dir, page_slugs)
        log_to_dashboard(f"[green]Completed crawl:[/] {site_dir}")
        return site_dir / "index.md"
