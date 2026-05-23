from notes_gen.output.formats import format_notes, format_prompt_suffix


def test_obsidian_passthrough():
    notes = "## Section\n\n[[Link]] and > [!TIP]\n> tip text"
    assert format_notes(notes, "obsidian") == notes


def test_unknown_format_passthrough():
    notes = "## Section\n\nContent."
    assert format_notes(notes, "unknown_fmt") == notes


def test_plain_removes_wikilinks():
    notes = "## Topic\n\nSee [[Python]] for details."
    result = format_notes(notes, "plain")
    assert "[[" not in result
    assert "Python" in result


def test_plain_removes_callouts():
    notes = "## Topic\n\n> [!TIP]\n> Use this approach.\n\nOther content."
    result = format_notes(notes, "plain")
    assert "[!TIP]" not in result
    assert "Other content" in result


def test_plain_removes_mermaid():
    notes = "## Flow\n\n```mermaid\ngraph TD\n A --> B\n```\n\nText after."
    result = format_notes(notes, "plain")
    assert "mermaid" not in result
    assert "Text after" in result


def test_logseq_converts_wikilinks_to_block_refs():
    notes = "## Topic\n\nSee [[Python]] for details."
    result = format_notes(notes, "logseq")
    assert "((Python))" in result
    assert "[[" not in result


def test_roam_converts_wikilinks_to_hashtag_refs():
    notes = "## Topic\n\nSee [[Python]] for details."
    result = format_notes(notes, "roam")
    assert "#[[Python]]" in result


def test_format_prompt_suffix_obsidian_empty():
    assert format_prompt_suffix("obsidian") == ""


def test_format_prompt_suffix_plain_has_instructions():
    suffix = format_prompt_suffix("plain")
    assert "plain" in suffix.lower()
    assert len(suffix) > 10


def test_format_prompt_suffix_logseq_has_instructions():
    suffix = format_prompt_suffix("logseq")
    assert "logseq" in suffix.lower() or "Logseq" in suffix


def test_format_prompt_suffix_roam_has_instructions():
    suffix = format_prompt_suffix("roam")
    assert "roam" in suffix.lower() or "Roam" in suffix
