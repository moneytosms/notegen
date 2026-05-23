from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_CACHE_DIR = Path.home() / ".cache" / "notegen"


def _key(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _cache_file(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def _read(key: str) -> str | None:
    f = _cache_file(key)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("content")
    except Exception:
        return None


def _write(key: str, content: str, url: str) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_file(key).write_text(
        json.dumps({
            "content": content,
            "url": url,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }),
        encoding="utf-8",
    )


def get_transcript_cache(url: str) -> str | None:
    return _read(_key(f"transcript:{url}"))


def set_transcript_cache(url: str, text: str) -> None:
    _write(_key(f"transcript:{url}"), text, url)


def get_notes_cache(url: str, model: str) -> str | None:
    return _read(_key(f"notes:{url}:{model}"))


def set_notes_cache(url: str, model: str, notes: str) -> None:
    _write(_key(f"notes:{url}:{model}"), notes, url)


def clear_cache() -> int:
    if not _CACHE_DIR.exists():
        return 0
    files = list(_CACHE_DIR.glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)
