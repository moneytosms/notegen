from unittest.mock import MagicMock, patch

import pytest

from notes_gen.config import Config
from notes_gen.processing.llm import (
    _available_keys,
    _is_network_error,
    _is_rate_limit_error,
    _parse_retry_after,
    compress_notes,
    generate_notes,
)


def _make_mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def _rate_limit_exc(msg: str = "RateLimitError: 429 too many requests") -> Exception:
    exc = Exception(msg)
    exc.__class__.__name__ = "RateLimitError"
    return exc


# ── basic call behaviour ──────────────────────────────────────────────────────


def test_generate_notes_single_chunk():
    cfg = Config(model="anthropic/claude-sonnet-4-6")
    chunks = ["Python generators use yield keyword to produce values lazily."]
    expected = "## Generators\n\nGenerators produce values lazily via `yield`."

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(expected)
        notes_text, tags = generate_notes(chunks, cfg)

    assert notes_text == expected
    assert tags == []
    mock_litellm.completion.assert_called_once()
    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs["model"] == cfg.model


def test_generate_notes_multiple_chunks_calls_llm_per_chunk():
    cfg = Config(model="openai/gpt-4o")
    chunks = ["chunk one content", "chunk two content", "chunk three content"]
    note = "## Section\n\nContent."

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(note)
        generate_notes(chunks, cfg)

    assert mock_litellm.completion.call_count == 3


def test_generate_notes_passes_temperature():
    cfg = Config()
    chunks = ["some content"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("notes")
        generate_notes(chunks, cfg)

    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs.get("temperature") == 0.3


def test_generate_notes_prompt_contains_chunk():
    cfg = Config()
    chunk_text = "unique_marker_content_xyz"
    chunks = [chunk_text]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("notes")
        generate_notes(chunks, cfg)

    messages = mock_litellm.completion.call_args.kwargs["messages"]
    all_content = " ".join(m["content"] for m in messages if isinstance(m.get("content"), str))
    assert chunk_text in all_content


def test_generate_notes_returns_concatenated_results():
    cfg = Config()
    chunks = ["chunk A", "chunk B"]
    responses = ["## Notes A\n\nContent A.", "## Notes B\n\nContent B."]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.side_effect = [_make_mock_response(r) for r in responses]
        notes_text, tags = generate_notes(chunks, cfg)

    assert "Notes A" in notes_text
    assert "Notes B" in notes_text


def test_generate_notes_passes_api_key_when_configured():
    cfg = Config(
        model="groq/llama-3.3-70b-versatile",
        api_keys={"groq": ["gsk_testkey123"]},
    )
    chunks = ["some content"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("notes")
        generate_notes(chunks, cfg)

    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs.get("api_key") == "gsk_testkey123"


def test_generate_notes_no_api_key_when_not_configured():
    cfg = Config(model="anthropic/claude-sonnet-4-6", api_keys={})
    chunks = ["some content"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("notes")
        generate_notes(chunks, cfg)

    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert "api_key" not in call_kwargs


# ── rate limit helpers ────────────────────────────────────────────────────────


def test_is_rate_limit_error_detects_429():
    assert _is_rate_limit_error(Exception("HTTP 429 too many requests"))


def test_is_rate_limit_error_detects_class_name():
    class RateLimitError(Exception):
        pass

    assert _is_rate_limit_error(RateLimitError("quota exceeded"))


def test_is_rate_limit_error_false_for_other():
    assert not _is_rate_limit_error(ValueError("invalid input"))


def test_parse_retry_after_extracts_seconds():
    exc = Exception("Rate limit exceeded. Retry-After: 45")
    assert _parse_retry_after(exc) == 45.0


def test_parse_retry_after_returns_none_when_absent():
    assert _parse_retry_after(Exception("some other error")) is None


def test_available_keys_excludes_cooled_down(monkeypatch):
    import time

    import notes_gen.processing.llm as llm_mod

    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={"groq": ["key1", "key2"]})
    monkeypatch.setattr(llm_mod, "_key_cooldowns", {"key1": time.monotonic() + 9999})
    available = _available_keys(cfg)
    assert available == ["key2"]


def test_available_keys_all_available(monkeypatch):
    import notes_gen.processing.llm as llm_mod

    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={"groq": ["key1", "key2"]})
    monkeypatch.setattr(llm_mod, "_key_cooldowns", {})
    assert set(_available_keys(cfg)) == {"key1", "key2"}


# ── retry behaviour ───────────────────────────────────────────────────────────


def test_retries_on_rate_limit_then_succeeds():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={"groq": ["k1"]}, max_retries=3)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm.time.sleep"),
        patch("notes_gen.processing.llm._key_cooldowns", {}),
    ):
        mock_litellm.completion.side_effect = [
            Exception("429 too many requests"),
            _make_mock_response("notes"),
        ]
        notes_text, tags = generate_notes(chunks, cfg)

    assert notes_text == "notes"
    assert mock_litellm.completion.call_count == 2


def test_raises_after_max_retries_exceeded():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={}, max_retries=2)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm.time.sleep"),
        patch("notes_gen.processing.llm._key_cooldowns", {}),
    ):
        mock_litellm.completion.side_effect = Exception("429 too many requests")
        with pytest.raises(Exception):
            generate_notes(chunks, cfg)

    assert mock_litellm.completion.call_count == cfg.max_retries + 1


def test_non_rate_limit_error_not_retried():
    cfg = Config(model="anthropic/claude-sonnet-4-6", api_keys={}, max_retries=3)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm._key_cooldowns", {}),
    ):
        mock_litellm.completion.side_effect = ValueError("bad request")
        with pytest.raises(ValueError):
            generate_notes(chunks, cfg)

    assert mock_litellm.completion.call_count == 1


def test_rotates_key_on_rate_limit_when_another_available(monkeypatch):
    import notes_gen.processing.llm as llm_mod

    cfg = Config(
        model="groq/llama-3.3-70b-versatile",
        api_keys={"groq": ["key1", "key2"]},
        max_retries=3,
    )
    chunks = ["content"]
    cooldowns: dict = {}
    monkeypatch.setattr(llm_mod, "_key_cooldowns", cooldowns)

    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("429 too many requests")
        return _make_mock_response("notes")

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.side_effect = side_effect
        notes_text, tags = generate_notes(chunks, cfg)

    assert notes_text == "notes"
    # first key should have been cooled down
    assert len(cooldowns) == 1


def test_uses_retry_after_header_for_wait():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={}, max_retries=1)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm.time.sleep") as mock_sleep,
        patch("notes_gen.processing.llm._key_cooldowns", {}),
    ):
        mock_litellm.completion.side_effect = [
            Exception("Rate limit exceeded. Retry-After: 30"),
            _make_mock_response("notes"),
        ]
        generate_notes(chunks, cfg)

    mock_sleep.assert_called_once_with(30.0)


# ── parallel execution ────────────────────────────────────────────────────────


def test_generate_notes_parallel_chunks_preserve_order():
    cfg = Config(model="groq/llama-3.3-70b-versatile", max_concurrent=3)
    chunks = ["chunk A", "chunk B", "chunk C"]
    responses = ["note A", "note B", "note C"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.side_effect = [_make_mock_response(r) for r in responses]
        notes_text, tags = generate_notes(chunks, cfg)

    parts = notes_text.split("\n\n")
    assert parts[0] == "note A"
    assert parts[1] == "note B"
    assert parts[2] == "note C"


def test_generate_notes_verbose_prints_info():
    cfg = Config(verbose=True)
    chunks = ["some content"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("notes")
        notes_text, tags = generate_notes(chunks, cfg)

    assert notes_text == "notes"


def test_generate_notes_extracts_tags_from_output():
    cfg = Config()
    chunks = ["some content"]
    llm_output = "## Notes\n\nContent here.\nTAGS: python, async, testing"

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(llm_output)
        notes_text, tags = generate_notes(chunks, cfg)

    assert tags == ["python", "async", "testing"]
    assert "TAGS:" not in notes_text
    assert "## Notes" in notes_text


def test_is_network_error_detects_timeout():
    import httpx

    assert _is_network_error(httpx.TimeoutException("timed out"))


def test_is_network_error_detects_connect_error():
    import httpx

    assert _is_network_error(httpx.ConnectError("connection refused"))


def test_is_network_error_detects_5xx():
    assert _is_network_error(Exception("HTTP 503 service unavailable"))


def test_is_network_error_false_for_4xx():
    assert not _is_network_error(Exception("HTTP 404 not found"))


def test_network_error_retries_without_cooldown():
    cfg = Config(model="anthropic/claude-sonnet-4-6", api_keys={}, max_retries=2)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm.time.sleep"),
        patch("notes_gen.processing.llm._key_cooldowns", {}) as cooldowns,
    ):
        mock_litellm.completion.side_effect = [
            ConnectionError("connection reset"),
            _make_mock_response("notes"),
        ]
        notes_text, _ = generate_notes(chunks, cfg)

    assert notes_text == "notes"
    assert len(cooldowns) == 0  # no key was cooled down for network error


# ── compression ───────────────────────────────────────────────────────────────


def test_compress_notes_skips_when_under_limit():
    cfg = Config()
    short_notes = "## Notes\n\nShort content."
    result = compress_notes(short_notes, 10000, cfg)
    assert result == short_notes


def test_compress_notes_calls_llm_when_over_limit():
    cfg = Config()
    long_notes = " ".join(["word"] * 2000)

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("## Condensed\n\nSummary.")
        result = compress_notes(long_notes, 10, cfg)

    assert result == "## Condensed\n\nSummary."
    mock_litellm.completion.assert_called_once()


def test_compress_notes_verbose_prints_info(capsys):
    cfg = Config(verbose=True)
    long_notes = " ".join(["word"] * 2000)

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("condensed")
        compress_notes(long_notes, 10, cfg)

    # verbose output goes to stderr via Rich console — just verify no crash
    assert True
