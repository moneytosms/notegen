# notes-gen — Task List

## Phase 1: Foundation

- [ ] Task 1: Project scaffold (pyproject.toml, package dirs, typer stub, ruff config)
- [ ] Task 2: Config system (Config dataclass, YAML load, CLI merge, config init/show)
- [ ] Task 3: Core processing pipeline (filter, chunker, llm wrapper, merger)
- [ ] Task 4: Output system (formatter, writer, overwrite prompt, index.md)
- [ ] **CHECKPOINT 1** — all tests pass, ruff clean, config commands work

## Phase 2: Text Pipeline

- [ ] Task 5: Text input → notes file (sources/text.py + CLI text command, end-to-end)
- [ ] **CHECKPOINT 2** — text → notes works with real LLM, output opens in Obsidian

## Phase 3: YouTube

- [ ] Task 6: YouTube single video (transcript fetch, metadata, loud failure on no captions)
- [ ] Task 7: YouTube playlist (parallel fetch, --force, topic grouping, index.md)
- [ ] **CHECKPOINT 3** — video + playlist produce correct Obsidian output

## Phase 4: Web

- [ ] Task 8: Web single page (httpx + trafilatura + bs4 fallback)
- [ ] Task 9: Web crawl (same-domain link following, depth/page limits)
- [ ] **CHECKPOINT 4** — web single + crawl work, depth/page limits respected

## Phase 5: Polish

- [ ] Task 10: Auto-detect source + rich progress bars
- [ ] **FINAL CHECKPOINT** — all tests ≥80% coverage, ruff clean, full manual smoke test
