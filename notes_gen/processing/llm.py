from __future__ import annotations

import litellm

from notes_gen.config import Config

_SYSTEM_PROMPT = """\
You are an expert note-taker converting transcripts and articles into structured Obsidian notes.

Rules:
- Use Obsidian-flavored markdown: YAML frontmatter (omit here — added externally),
  ## and ### headings only
- Use `> [!TIP]` and `> [!WARNING]` callouts for important insights
- Use mermaid diagrams for flows and architectures when appropriate
- Use [[wikilinks]] for cross-references to related concepts
- Be comprehensive — never truncate to hit a length limit
- Auto-infer relevant tags from content
- Write for a technical audience learning the subject
"""

_USER_PROMPT_TEMPLATE = """\
Convert the following content into structured Obsidian notes:

<content>
{chunk}
</content>

Produce well-organized markdown notes with clear headings, key concepts,
code examples where relevant, and callouts for important points.
"""


def generate_notes(chunks: list[str], cfg: Config) -> str:
    results: list[str] = []
    for chunk in chunks:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(chunk=chunk)},
        ]
        response = litellm.completion(
            model=cfg.model,
            messages=messages,
            temperature=0.3,
        )
        results.append(response.choices[0].message.content)
    return "\n\n".join(results)
