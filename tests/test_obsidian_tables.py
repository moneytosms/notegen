import re
import sys


def verify_obsidian_table(markdown_text):
    """
    Verifies if a markdown table follows Obsidian-friendly rules:
    1. Leading and trailing pipes on every row.
    2. Separator row has at least 3 dashes.
    3. Pipes in wikilinks are escaped.
    """
    lines = [ln.strip() for ln in markdown_text.strip().split("\n") if ln.strip()]
    if len(lines) < 2:
        return False, "Not enough lines for a table"

    # 1. Check leading/trailing pipes
    for i, line in enumerate(lines):
        if not (line.startswith("|") and line.endswith("|")):
            return False, f"Line {i + 1} missing leading or trailing pipe: {line}"

    # 2. Check separator row (usually 2nd line)
    sep_row = lines[1]
    # Simplified check: must contain | and -
    if "-" not in sep_row:
        return False, f"Line 2 does not look like a separator row: {sep_row}"

    # Check for at least 3 dashes in at least one cell
    cells = [c.strip() for c in sep_row.split("|") if c.strip()]
    if not any(c.count("-") >= 3 for c in cells):
        return False, f"Separator row cells need at least 3 dashes: {sep_row}"

    # 3. Check for unescaped pipes in wikilinks
    # Pattern: [[ followed by text, then a | (not escaped), then text, then ]]
    # This is tricky because negative lookbehind is better but we can just check for [[ and ]]
    wikilink_matches = re.findall(r"\[\[(.*?)\]\]", markdown_text)
    for link in wikilink_matches:
        if "|" in link:
            # Check if it's escaped
            if not link.replace("\\|", "").count("|") == 0:
                return False, f"Unescaped pipe in wikilink: [[{link}]]"

    return True, "Table follows Obsidian-friendly rules"


# Sample output to test
test_output = r"""
| Category | Item | Description |
| :--- | :---: | ---: |
| Software | Obsidian | A powerful knowledge base |
| Format | Markdown | Simple text-based formatting |
| Link | [[Note\|Alias]] | Wikilink with an alias |
"""

success, msg = verify_obsidian_table(test_output)
print(f"Test Result: {'PASS' if success else 'FAIL'}")
print(f"Message: {msg}")

if not success:
    sys.exit(1)
