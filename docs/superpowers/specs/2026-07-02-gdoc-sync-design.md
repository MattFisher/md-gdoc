# gdoc-sync: Local markdown ↔ Google Docs collaboration tool

**Date:** 2026-07-02
**Status:** Approved design, pending implementation plan

## Problem

Discussion documents are drafted locally in markdown with an AI agent, then shared
with teammates who comment and edit in Google Docs. Today the round trip is manual:
"paste from markdown" into a Doc, hand-copy comments back into a local text file,
"copy as markdown" for edits (which introduces spurious escape characters). This
loses time and fidelity in both directions.

## Goals

- Push a local markdown file to a Google Doc with one command.
- Pull teammate feedback (comments with anchors and reply threads, plus direct
  edits to the text) back into agent-readable local files with one command.
- Preserve Google Docs comment anchors across revision pushes wherever the
  anchored text did not change.
- Fix the escape-character problem in code, once.
- Teammates change nothing about how they work: they get a normal Google Doc.

## Non-goals (v1)

- Posting replies or resolving comment threads from local side. The data model
  must not preclude this (comment IDs are retained), but no code is built for it.
- Handling Google Docs suggestion-mode edits as structured data. Suggestions
  that teammates accept become direct edits and flow through the normal pull.
- Real-time sync. This is an explicit push/pull tool for review rounds.
- Images, tables, and footnotes round-tripping perfectly. v1 targets prose:
  headings, paragraphs, bold/italic, links, lists, block quotes. Anything else
  should survive push (via the fallback path) but may not diff cleanly.

## Architecture

A standalone Python CLI (`gdoc-sync`) in its own repo, installable so it can be
run against markdown files in any project (work discussion docs, Substack
drafts). Uses `google-api-python-client` with OAuth user credentials (Workspace account;
API access is permitted). Scopes: `drive.file` (docs the app creates/opens) and
Drive comments read access.

### Data model

- **Frontmatter binding.** After first push, the tool writes `gdoc_id` (and
  `gdoc_url` for convenience) into the markdown file's YAML frontmatter. This
  binds file ↔ doc; all later commands read it from there.
- **Snapshot (merge base).** `.sync/<filename>.base.md` stores the markdown as
  of the last successful push. Used by `pull` to diff remote edits and by
  `push` to compute the paragraph-level revision diff. Directory is
  git-ignored.
- **Comments file.** `pull` writes `<filename>.comments.md` next to the source
  file: one section per comment thread, containing comment ID, author, created/
  modified times, resolved status, the quoted anchor text, the comment body,
  and nested replies. Format is plain markdown, ordered by position in the doc,
  designed to be read by the agent alongside the draft.

### Commands

#### `push <file.md>`

- **First push (no `gdoc_id` in frontmatter):** upload the markdown via the
  Drive API with conversion (`text/markdown` → Google Doc). Write `gdoc_id`
  and `gdoc_url` to frontmatter, save the snapshot, print the shareable URL.
- **Revision push (`gdoc_id` present):** preserve comment anchors:
  1. Diff current markdown against the snapshot at paragraph granularity
     (a paragraph = markdown block: heading, paragraph, list item, quote).
  2. Read the live doc structure via `documents.get` to map paragraphs to
     index ranges. Verify unchanged paragraphs still match the doc text; if
     the doc has diverged from the snapshot (teammate edits not yet pulled),
     abort with "remote has changes — run pull first" unless `--force`.
  3. Translate every changed/inserted/deleted block into
     `deleteContentRange`, `insertText`, and formatting requests
     (`updateTextStyle`, `updateParagraphStyle`, bullets) for that region
     only, ordered tail-to-head so earlier indexes stay valid, and apply
     them all in one `batchUpdate` call so the push is atomic. Untouched
     paragraphs are never rewritten, so their comment anchors survive.
  4. Before applying, cross-reference the diff against unresolved comment
     anchors and warn: "this push will orphan N comment(s): …" with a
     confirmation prompt (`--yes` to skip).
  5. Update the snapshot on success.
- **`push --replace`:** escape hatch that re-imports the whole file (Drive
  update-with-conversion), orphaning all anchors. Used for structural rewrites
  or when the diff path fails. The tool prints a clear warning first.

#### `pull <file.md>`

1. **Export content:** `files.export` as `text/markdown`, then run the
   unescape pass: strip Google's spurious backslash-escaping of markdown
   punctuation (`\-`, `\+`, `\.`, `\[`, etc.) except where escaping is
   semantically required. Normalize line endings and heading spacing so
   diffs against local files are quiet.
2. **Fetch comments:** Drive `comments.list` with replies, including resolved
   threads (marked as such). Write `<filename>.comments.md` as described above.
3. **Surface remote edits:** diff the cleaned export against the snapshot.
   - No remote changes: report "no edits; N comments pulled."
   - Remote changes, local file unchanged since snapshot: apply the remote
     version directly to the local file (frontmatter preserved) and update
     the snapshot.
   - Both sides changed: write the export to `<filename>.remote.md` and print
     a three-way summary; the agent merges (it has base, local, remote). The
     tool does not attempt automatic merge in v1.

#### `status <file.md>`

Read-only convenience: shows doc URL, whether remote content differs from the
snapshot, and unresolved comment count. Cheap way to check "is there feedback?"

### Auth

Standard installed-app OAuth flow; token cached at
`~/.config/gdoc-sync/token.json` with refresh. First run opens a browser for
consent. No service account (docs must be owned/shared by the user's identity
so teammates see a normal shared doc).

## Error handling

- Missing/invalid `gdoc_id` (doc deleted, access revoked): clear message,
  suggest removing frontmatter keys to re-push fresh.
- Snapshot missing (fresh clone): `pull` still works (export + comments) but
  treats everything as "both changed" → writes `.remote.md`; `push` requires
  `--replace` or a prior pull.
- `batchUpdate` failures: all block operations go in one atomic call, so a
  rejected batch applies nothing and the snapshot is not updated. If partial
  application is ever detected (doc revision advanced despite an error),
  instruct the user to `pull` and inspect.
- Markdown constructs the differ can't map (tables, images, footnotes):
  detected up front; the tool names the offending blocks and offers
  `--replace`.

## Testing

- Unit tests (pytest, no network): the unescape pass (fixture pairs of
  Google-exported markdown → clean markdown), paragraph diffing (base/new →
  expected block operations), markdown block → `batchUpdate` request
  generation, frontmatter read/write.
- Integration smoke test (manual, documented in the repo README): push a
  fixture doc, comment on it by hand, edit a paragraph, `pull`, verify
  comments file and remote diff; revise an untouched-comment paragraph's
  sibling, `push`, verify the comment anchor survived in the Docs UI.

## Future work (explicitly designed-for, not built)

- `reply <file.md> <comment-id> "text"` and `resolve <comment-id>`: the
  comments file already carries comment IDs, so these are additive commands
  against `replies.create` / comment resolution.
- Auto-merge for the "both sides changed" pull case.
- Multiple reviewers' docs from one source file, if ever needed.

## Workflow (end state)

1. Draft `doc.md` locally with the agent.
2. `gdoc-sync push doc.md` → share the printed URL.
3. Teammates comment and edit in Google Docs as they always have.
4. `gdoc-sync pull doc.md` → agent reads `doc.comments.md` (+ `.remote.md`
   if both sides changed) and revises.
5. `gdoc-sync push doc.md` → anchors on unchanged paragraphs survive;
   warned about any that won't.
6. Repeat until done; resolve comments in the Docs UI when glancing at it
   (until the reply/resolve commands exist).
