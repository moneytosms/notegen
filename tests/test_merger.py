from notes_gen.processing.merger import _jaccard_similarity, merge


def test_merge_single_note():
    notes = ["## Overview\n\nContent here."]
    result = merge(notes)
    assert "Overview" in result
    assert "Content here" in result


def test_merge_multiple_distinct_sections():
    notes = [
        "## Section A\n\nContent A.",
        "## Section B\n\nContent B.",
    ]
    result = merge(notes)
    assert "Section A" in result
    assert "Section B" in result


def test_merge_deduplicates_identical_headers():
    notes = [
        "## Introduction\n\nFirst intro.",
        "## Introduction\n\nSecond intro (duplicate header).",
        "## Conclusion\n\nThe end.",
    ]
    result = merge(notes)
    # Only one Introduction section should remain
    assert result.count("## Introduction") == 1
    assert "Conclusion" in result


def test_merge_empty_list():
    assert merge([]) == ""


def test_merge_empty_strings_ignored():
    notes = ["", "## Real Section\n\nContent.", ""]
    result = merge(notes)
    assert "Real Section" in result


def test_merge_preserves_order_of_first_occurrence():
    notes = [
        "## Alpha\n\nFirst.",
        "## Beta\n\nSecond.",
        "## Alpha\n\nDuplicate alpha.",
    ]
    result = merge(notes)
    alpha_pos = result.index("## Alpha")
    beta_pos = result.index("## Beta")
    assert alpha_pos < beta_pos


# ── Jaccard similarity ────────────────────────────────────────────────────────


def test_jaccard_identical_texts():
    assert _jaccard_similarity("the quick brown fox", "the quick brown fox") == 1.0


def test_jaccard_disjoint_texts():
    assert _jaccard_similarity("alpha beta gamma", "delta epsilon zeta") == 0.0


def test_jaccard_partial_overlap():
    score = _jaccard_similarity("alpha beta gamma delta", "alpha beta epsilon zeta")
    assert 0.0 < score < 1.0


def test_jaccard_empty_strings():
    assert _jaccard_similarity("", "") == 0.0
    assert _jaccard_similarity("words here", "") == 0.0


# ── Fuzzy section dedup ───────────────────────────────────────────────────────

_LONG_BODY = " ".join(["word"] * 60)


def test_fuzzy_dedup_removes_near_duplicate_sections():
    # 55 shared unique words + 5 unique to each → jaccard = 55/(55+5+5) ≈ 0.85
    shared = [f"word{i}" for i in range(55)]
    body_a = " ".join(shared + [f"onlya{i}" for i in range(5)])
    body_b = " ".join(shared + [f"onlyb{i}" for i in range(5)])
    notes = [
        f"## Section A\n\n{body_a}",
        f"## Section B\n\n{body_b}",
    ]
    result = merge(notes, similarity_threshold=0.7)
    assert "Section A" in result
    assert "Section B" not in result


def test_fuzzy_dedup_keeps_distinct_sections():
    body_a = " ".join([f"apple{i}" for i in range(60)])
    body_b = " ".join([f"banana{i}" for i in range(60)])
    notes = [
        f"## Section A\n\n{body_a}",
        f"## Section B\n\n{body_b}",
    ]
    result = merge(notes, similarity_threshold=0.7)
    assert "Section A" in result
    assert "Section B" in result


def test_fuzzy_dedup_skips_short_sections():
    notes = [
        "## Short A\n\nBrief.",
        "## Short B\n\nBrief.",
    ]
    result = merge(notes, similarity_threshold=0.7)
    # Short sections (< 50 words) skip similarity check — both kept
    assert "Short A" in result
    assert "Short B" in result
