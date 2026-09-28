# Knowledge Engine

The Knowledge Engine stores, processes, and manages trading knowledge used by Moil Bot.

## Directory Structure

- `sources/` — Initial and external trading knowledge sources.
- `documents/` — Source documents such as PDFs and other reference material.
- `extracted/` — Text and structured information extracted from source documents.
- `concepts/` — Trading concepts identified from extracted knowledge.
- `rules/` — Versioned trading strategy rules derived from knowledge.
- `registry/` — Metadata and records for registered knowledge sources.
- `consolidated/` — Consolidated knowledge prepared for use by the bot.
- `tests/` — Tests for Knowledge Engine components.

The Knowledge Engine is developed incrementally through M03 issues.
