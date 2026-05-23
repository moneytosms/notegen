from __future__ import annotations

from pathlib import Path


def write_note(
    path: Path,
    content: str,
    overwrite_policy: str = "overwrite",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if overwrite_policy == "skip":
            return path
        if overwrite_policy == "rename":
            stem = path.stem
            suffix = path.suffix
            counter = 1
            new_path = path.parent / f"{stem}-{counter}{suffix}"
            while new_path.exists():
                counter += 1
                new_path = path.parent / f"{stem}-{counter}{suffix}"
            new_path.write_text(content, encoding="utf-8")
            return new_path

    path.write_text(content, encoding="utf-8")
    return path


def write_index(playlist_dir: Path, video_slugs: list[str]) -> Path:
    playlist_dir.mkdir(parents=True, exist_ok=True)
    title = playlist_dir.name.replace("-", " ").title()
    lines = [f"# {title}\n"]
    for slug in video_slugs:
        lines.append(f"- [[{slug}]]")
    content = "\n".join(lines) + "\n"
    index_path = playlist_dir / "index.md"
    index_path.write_text(content, encoding="utf-8")
    return index_path
