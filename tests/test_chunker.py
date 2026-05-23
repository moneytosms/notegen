from notes_gen.processing.chunker import chunk_text, count_tokens


def test_count_tokens_basic():
    n = count_tokens("hello world")
    assert n > 0
    assert isinstance(n, int)


def test_chunk_text_short_returns_single_chunk():
    text = "This is a short text."
    chunks = chunk_text(text, max_tokens=12000, overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_returns_empty():
    chunks = chunk_text("", max_tokens=12000, overlap=200)
    assert chunks == []


def test_chunk_text_splits_long_text():
    # ~30 tokens each line, build ~600 token text
    line = "The quick brown fox jumps over the lazy dog and then runs away fast. " * 3
    text = (line + "\n") * 30
    chunks = chunk_text(text, max_tokens=200, overlap=20)
    assert len(chunks) > 1


def test_chunk_text_respects_max_tokens():
    line = "word " * 100  # ~100 tokens
    text = (line + "\n") * 20  # ~2000 tokens
    chunks = chunk_text(text, max_tokens=300, overlap=30)
    for chunk in chunks:
        token_count = count_tokens(chunk)
        assert token_count <= 300 + 50  # allow small overshoot at boundaries


def test_chunk_text_overlap_shares_content():
    word = "unique_word_"
    words = [f"{word}{i}" for i in range(500)]
    text = " ".join(words)
    chunks = chunk_text(text, max_tokens=100, overlap=20)
    assert len(chunks) >= 2
    # last tokens of chunk N should appear in chunk N+1
    last_words = chunks[0].split()[-5:]
    second_chunk_words = chunks[1].split()
    assert any(w in second_chunk_words for w in last_words)


def test_chunk_text_no_data_loss():
    words = [f"w{i}" for i in range(1000)]
    text = " ".join(words)
    chunks = chunk_text(text, max_tokens=150, overlap=15)
    joined = " ".join(chunks)
    for word in words:
        assert word in joined
