# md-gdoc

Sync local markdown files with Google Docs: push drafts, pull comments and
edits, preserve comment anchors across revisions.

Design: `docs/superpowers/specs/2026-07-02-gdoc-sync-design.md`

## Setup

```bash
uv sync
```

## Usage

```bash
uv run md-gdoc push draft.md      # first push creates the doc, binds gdoc_id
uv run md-gdoc status draft.md    # any feedback yet?
uv run md-gdoc pull draft.md      # comments -> draft.md.comments.md; edits merged
uv run md-gdoc push draft.md      # revision push, preserves comment anchors
uv run md-gdoc push draft.md --replace   # full re-import (orphans all anchors)
```

Auth: create a Google Cloud OAuth *desktop* client, save its JSON to
`~/.config/md-gdoc/credentials.json` (or set `MD_GDOC_CREDENTIALS`).
First run opens a browser. Token cached at `~/.config/md-gdoc/token.json`.

Add to consuming repos' `.gitignore`: `.sync/`, `*.comments.md`, `*.remote.md`.

## Test

```bash
uv run pytest              # unit tests, no network
```

## End-to-end tests (opt-in)

```bash
RUN_MD_GDOC_E2E=1 uv run pytest tests/e2e -q
```

Requires OAuth credentials (see Auth). Creates and deletes real docs in the
Drive folder `md-gdoc-e2e` (override: MD_GDOC_E2E_FOLDER). Regenerate the
golden export: `RUN_MD_GDOC_E2E=1 python -m tests.e2e.test_end_to_end --generate`
