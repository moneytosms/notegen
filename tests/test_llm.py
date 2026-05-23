from unittest.mock import MagicMock, patch

from notes_gen.config import Config
from notes_gen.processing.llm import generate_notes


def _make_mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def test_generate_notes_single_chunk():
    cfg = Config(model="anthropic/claude-sonnet-4-6")
    chunks = ["Python generators use yield keyword to produce values lazily."]
    expected = "## Generators\n\nGenerators produce values lazily via `yield`."

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(expected)
        result = generate_notes(chunks, cfg)

    assert result == expected
    mock_litellm.completion.assert_called_once()
    call_kwargs = mock_litellm.completion.call_args
    assert call_kwargs.kwargs["model"] == cfg.model or call_kwargs.args[0] == cfg.model


def test_generate_notes_multiple_chunks_calls_llm_per_chunk():
    cfg = Config(model="openai/gpt-4o")
    chunks = ["chunk one content", "chunk two content", "chunk three content"]
    note = "## Section\n\nContent."

    with patch("notes_gen.processing.llm.litellm") as mock_litellm:
        mock_litellm.completion.return_value = _make_mock_response(note)
        result = generate_notes(chunks, cfg)

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
        result = generate_notes(chunks, cfg)

    assert "Notes A" in result
    assert "Notes B" in result
