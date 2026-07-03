# gdoc-sync

Sync local markdown files with Google Docs: push drafts, pull comments and
edits, preserve comment anchors across revisions.

Design: `docs/superpowers/specs/2026-07-02-gdoc-sync-design.md`

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
```

## Usage

```bash
gdoc-sync push draft.md      # first push creates the doc, binds gdoc_id
gdoc-sync status draft.md    # any feedback yet?
gdoc-sync pull draft.md      # comments -> draft.md.comments.md; edits merged
gdoc-sync push draft.md      # revision push, preserves comment anchors
gdoc-sync push draft.md --replace   # full re-import (orphans all anchors)
```

Auth: create a Google Cloud OAuth *desktop* client, save its JSON to
`~/.config/gdoc-sync/credentials.json` (or set `GDOC_SYNC_CREDENTIALS`).
First run opens a browser. Token cached at `~/.config/gdoc-sync/token.json`.

Add to consuming repos' `.gitignore`: `.sync/`, `*.comments.md`, `*.remote.md`.

## Test

```bash
pytest              # unit tests, no network
```

## End-to-end tests (opt-in)

```bash
RUN_GDOC_SYNC_E2E=1 pytest tests/e2e -q
```

Requires OAuth credentials (see Auth). Creates and deletes real docs in the
Drive folder `gdoc-sync-e2e` (override: GDOC_SYNC_E2E_FOLDER). Regenerate the
golden export: `RUN_GDOC_SYNC_E2E=1 python -m tests.e2e.test_end_to_end --generate`
