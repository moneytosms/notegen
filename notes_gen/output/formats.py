from __future__ import annotations

import re

_VALID_FORMATS = {"obsidian", "logseq", "plain", "roam"}

_FORMAT_PROMPTS: dict[str, str] = {
    "obsidian": (
        "\nOutput format: Obsidian-flavored markdown. "
        "For tables, always use the following format with leading/trailing pipes"
        " and explicit alignment:\n\n"
        "| Header 1 | Header 2 |\n"
        "| :------- | :------- |\n"
        "| Cell 1   | Cell 2   |\n\n"
        "Rules: pipes at start/end of every row, at least 3 dashes in separator,"
        " no empty lines within table, escape pipes in wikilinks: [[Link\\|Alias]]."
    ),
    "logseq": (
        "\nOutput format: Logseq. Use bullet-based indented structure. "
        "Replace [[wikilinks]] with ((block-refs)) where appropriate. "
        "Replace callouts with #+BEGIN_TIP / #+END_TIP blocks."
    ),
    "plain": (
        "\nOutput format: plain markdown. No wikilinks, no callouts, no mermaid diagrams. "
        "Use standard headings and paragraphs only."
    ),
    "roam": (
        "\nOutput format: Roam Research. Use #[[tags]] for concepts. "
        "Use {{[[TODO]]}} for action items. Nest content as bullets."
    ),
}


def format_prompt_suffix(output_format: str) -> str:
    return _FORMAT_PROMPTS.get(output_format, "")


def format_notes(notes: str, output_format: str) -> str:
    if output_format == "obsidian" or output_format not in _VALID_FORMATS:
        return notes
    if output_format == "plain":
        return _to_plain(notes)
    if output_format == "logseq":
        return _to_logseq(notes)
    if output_format == "roam":
        return _to_roam(notes)
    return notes


def _to_plain(notes: str) -> str:
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", notes)
    text = re.sub(r"^> \[!(?:TIP|WARNING|NOTE|INFO)\]\s*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^> ", "", text, flags=re.MULTILINE)
    text = re.sub(r"```mermaid.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _callout_to_block(tag: str) -> re.Pattern:
    return re.compile(rf"^> \[!{tag}\]\s*\n((?:^> .*\n?)*)", re.MULTILINE)


def _strip_gt(body: str) -> str:
    return re.sub(r"^> ", "", body, flags=re.MULTILINE)


def _to_logseq(notes: str) -> str:
    text = re.sub(r"\[\[([^\]]+)\]\]", r"((\1))", notes)
    text = _callout_to_block("TIP").sub(
        lambda m: f"#+BEGIN_TIP\n{_strip_gt(m.group(1))}#+END_TIP\n", text
    )
    text = _callout_to_block("WARNING").sub(
        lambda m: f"#+BEGIN_WARNING\n{_strip_gt(m.group(1))}#+END_WARNING\n", text
    )
    return text.strip()


def _to_roam(notes: str) -> str:
    text = re.sub(r"\[\[([^\]]+)\]\]", r"#[[\1]]", notes)
    return text.strip()
