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
    llm_output = expected + "\nTAGS: python, async"

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(llm_output)
        notes_text, tags = generate_notes(chunks, cfg)

    assert notes_text == expected
    assert tags == ["python", "async"]
    mock_litellm.completion.assert_called_once()
    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs["model"] == cfg.model


def test_generate_notes_multiple_chunks_calls_llm_per_chunk():
    cfg = Config(model="openai/gpt-4o")
    chunks = ["chunk one", "chunk two", "chunk three"]
    note = "## Section\n\nContent.\nTAGS: tag"

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(note)
        generate_notes(chunks, cfg)

    # 3 chunks * 1 call each (if TAGS: is present)
    assert mock_litellm.completion.call_count == 3


def test_generate_notes_passes_temperature():
    cfg = Config()
    chunks = ["some content"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response("notes\nTAGS: t")
        generate_notes(chunks, cfg)

    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs.get("temperature") == 0.3


def test_generate_notes_returns_concatenated_results():
    cfg = Config()
    chunks = ["chunk A", "chunk B"]
    responses = ["## Notes A\n\nContent A.\nTAGS: a", "## Notes B\n\nContent B.\nTAGS: b"]

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.side_effect = [_make_mock_response(r) for r in responses]
        notes_text, tags = generate_notes(chunks, cfg)

    assert "Notes A" in notes_text
    assert "Notes B" in notes_text


# ── rate limit helpers ────────────────────────────────────────────────────────


def test_is_rate_limit_error_detects_429():
    assert _is_rate_limit_error(Exception("HTTP 429 too many requests"))


def test_parse_retry_after_extracts_seconds():
    exc = Exception("Rate limit exceeded. Retry-After: 45")
    assert _parse_retry_after(exc) == 45.0


# ── retry behaviour ───────────────────────────────────────────────────────────


def test_retries_on_rate_limit_then_succeeds():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={"groq": ["k1"]}, max_retries=3, retry_base_delay=0.1)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm.time.sleep"),
        patch("notes_gen.processing.llm._key_cooldowns", {}),
    ):
        mock_litellm.completion.side_effect = [
            Exception("429 too many requests"),
            _make_mock_response("notes\nTAGS: t"),
        ]
        notes_text, tags = generate_notes(chunks, cfg)

    assert notes_text == "notes"
    assert mock_litellm.completion.call_count == 2


def test_network_error_retries_without_cooldown():
    cfg = Config(model="anthropic/claude-sonnet-4-6", api_keys={}, max_retries=2, retry_base_delay=0.1)
    chunks = ["content"]

    with (
        patch("notes_gen.processing.llm.litellm") as mock_litellm,
        patch("notes_gen.processing.llm.time.sleep"),
        patch("notes_gen.processing.llm._key_cooldowns", {}) as cooldowns,
    ):
        mock_litellm.completion.side_effect = [
            ConnectionError("connection reset"),
            _make_mock_response("notes\nTAGS: t"),
        ]
        notes_text, _ = generate_notes(chunks, cfg)

    assert notes_text == "notes"
    assert len(cooldowns) == 0


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
