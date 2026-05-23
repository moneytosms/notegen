from unittest.mock import patch


def _patched_cache_dir(tmp_path):
    import notes_gen.cache as cache_mod

    return patch.object(cache_mod, "_CACHE_DIR", tmp_path / "notegen")


def test_transcript_cache_miss(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import get_transcript_cache

        assert get_transcript_cache("https://example.com/video") is None


def test_transcript_cache_hit(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import get_transcript_cache, set_transcript_cache

        set_transcript_cache("https://example.com/video", "hello world")
        assert get_transcript_cache("https://example.com/video") == "hello world"


def test_notes_cache_miss(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import get_notes_cache

        assert get_notes_cache("https://example.com", "anthropic/claude") is None


def test_notes_cache_hit(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import get_notes_cache, set_notes_cache

        set_notes_cache("https://example.com", "anthropic/claude", "## Notes\n\nContent.")
        assert get_notes_cache("https://example.com", "anthropic/claude") == "## Notes\n\nContent."


def test_notes_cache_model_isolation(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import get_notes_cache, set_notes_cache

        set_notes_cache("https://x.com", "model-a", "notes from a")
        assert get_notes_cache("https://x.com", "model-b") is None


def test_clear_cache(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import clear_cache, set_transcript_cache

        set_transcript_cache("https://a.com", "content a")
        set_transcript_cache("https://b.com", "content b")
        removed = clear_cache()
        assert removed == 2
        assert get_transcript_cache_after_clear(tmp_path) is None


def get_transcript_cache_after_clear(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import get_transcript_cache

        return get_transcript_cache("https://a.com")


def test_clear_cache_empty_dir(tmp_path):
    with _patched_cache_dir(tmp_path):
        from notes_gen.cache import clear_cache

        assert clear_cache() == 0


def test_cache_file_contains_metadata(tmp_path):
    import json

    with _patched_cache_dir(tmp_path) as patched_dir:
        from notes_gen.cache import set_transcript_cache

        set_transcript_cache("https://example.com/x", "the content")
        files = list((tmp_path / "notegen").glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["content"] == "the content"
        assert data["url"] == "https://example.com/x"
        assert "cached_at" in data
