# gdoc-sync

Sync local markdown files with Google Docs: push drafts, pull comments and
edits, preserve comment anchors across revisions.

Design: `docs/superpowers/specs/2026-07-02-gdoc-sync-design.md`

## Setup

    python -m venv .venv && . .venv/bin/activate
    pip install -e '.[dev]'

## Test

    pytest              # unit tests, no network
