from notes_gen.processing.merger import merge


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
