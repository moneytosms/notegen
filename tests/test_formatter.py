from datetime import date

from notes_gen.output.formatter import build_frontmatter, generate_toc, slugify


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert slugify("FastAPI Tutorial #1!") == "fastapi-tutorial-1"


def test_slugify_multiple_spaces():
    assert slugify("  too   many   spaces  ") == "too-many-spaces"


def test_slugify_unicode():
    result = slugify("Ünïcödé Têst")
    assert result == result.lower()
    assert " " not in result


def test_slugify_empty():
    assert slugify("") == ""


def test_slugify_already_slug():
    assert slugify("already-a-slug") == "already-a-slug"


def test_build_frontmatter_basic():
    fm = build_frontmatter(
        title="Test Note",
        source="https://example.com",
        type="article",
        tags=["python", "testing"],
        date=date(2024, 1, 15),
    )
    assert fm.startswith("---\n")
    assert fm.endswith("---\n")
    assert "title: Test Note" in fm
    assert "source: https://example.com" in fm
    assert "type: article" in fm
    assert "python" in fm
    assert "2024-01-15" in fm


def test_build_frontmatter_video_type():
    fm = build_frontmatter(
        title="My Video",
        source="https://youtube.com/watch?v=xyz",
        type="video",
        tags=["video"],
        date=date(2024, 3, 1),
    )
    assert "type: video" in fm


def test_build_frontmatter_empty_tags():
    fm = build_frontmatter(
        title="No Tags",
        source="https://example.com",
        type="article",
        tags=[],
        date=date(2024, 1, 1),
    )
    assert "---" in fm
    assert "title: No Tags" in fm


def test_build_frontmatter_is_valid_yaml():
    import yaml

    fm = build_frontmatter(
        title="Valid YAML",
        source="https://example.com",
        type="article",
        tags=["a", "b"],
        date=date(2024, 6, 15),
    )
    inner = fm.strip().removeprefix("---").removesuffix("---").strip()
    parsed = yaml.safe_load(inner)
    assert parsed["title"] == "Valid YAML"
    assert parsed["type"] == "article"


_NOTES_WITH_MANY_HEADERS = """\
# The Title

## Introduction

Some text.

## Core Concepts

More text.

### Sub-concept A

Detail.

### Sub-concept B

Detail.

## Conclusion

Final thoughts.
"""


def test_generate_toc_inserts_contents_block():
    result = generate_toc(_NOTES_WITH_MANY_HEADERS)
    assert "## Contents" in result
    assert "[[#Introduction|Introduction]]" in result
    assert "[[#Core Concepts|Core Concepts]]" in result
    assert "  - [[#Sub-concept A|Sub-concept A]]" in result


def test_generate_toc_inserted_after_title():
    result = generate_toc(_NOTES_WITH_MANY_HEADERS)
    title_pos = result.index("# The Title")
    toc_pos = result.index("## Contents")
    intro_pos = result.index("## Introduction")
    assert title_pos < toc_pos < intro_pos


def test_generate_toc_skips_when_few_headers():
    notes = "# Title\n\n## Only\n\nOne section.\n"
    result = generate_toc(notes)
    assert result == notes
    assert "## Contents" not in result


def test_generate_toc_passthrough_when_no_title():
    notes = "## Section A\n\n## Section B\n\n## Section C\n\n## Section D\n"
    result = generate_toc(notes)
    assert "## Contents" in result
    # TOC at top since no # heading
    assert result.startswith("## Contents")
