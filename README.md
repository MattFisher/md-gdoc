# md-gdoc

[![CI](https://github.com/MattFisher/md-gdoc/actions/workflows/ci.yml/badge.svg)](https://github.com/MattFisher/md-gdoc/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/md-gdoc)](https://pypi.org/project/md-gdoc/) [![Python](https://img.shields.io/pypi/pyversions/md-gdoc)](https://pypi.org/project/md-gdoc/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Sync local markdown files with Google Docs: push drafts, pull comments and edits, and preserve comment anchors across revisions.

You write in markdown (perhaps with an AI agent alongside); your reviewers comment and edit in a normal Google Doc. md-gdoc does the round trip that is otherwise manual copy-paste:

```console
$ md-gdoc push draft.md          # creates the doc, links it in frontmatter
Created doc: https://docs.google.com/document/d/…/edit

$ md-gdoc status draft.md        # any feedback yet?
Remote changes: yes
Open comments: 3

$ md-gdoc pull draft.md          # comments -> draft.md.comments.md; edits merged
3 comment(s) pulled.
Remote edits applied to local file.

$ md-gdoc push draft.md          # revised draft; comment anchors preserved
Pushed: https://docs.google.com/document/d/…/edit
```

> **Status: alpha.** md-gdoc works end-to-end and has a thorough test suite, but it has had few users and its interfaces may change between 0.x releases.

## Install

```bash
uv tool install md-gdoc     # or: pipx install md-gdoc, or: pip install md-gdoc
```

## Google API setup (one-time)

md-gdoc talks to Google as *you*, via an OAuth "desktop app" client that you create in your own Google Cloud project. Nothing is hosted anywhere; tokens stay on your machine.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project (any name).
2. Enable the **Google Docs API** and the **Google Drive API** (*APIs & Services → Library*).
3. Configure the OAuth consent screen (*APIs & Services → OAuth consent screen*): user type **External** is fine; add your own Google account as a test user. The app can stay in "Testing" mode.
4. Create credentials: *APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app*.
5. Download the client JSON and save it to `~/.config/md-gdoc/credentials.json`.

The first command you run opens a browser window to authorize; the resulting token is cached at `~/.config/md-gdoc/token.json` and refreshed automatically.

Environment overrides: `MD_GDOC_CREDENTIALS` (client secrets path) and `MD_GDOC_TOKEN` (token cache path).

### A note on permissions

md-gdoc requests the full `https://www.googleapis.com/auth/drive` scope. This is deliberate: `clone` and `pull` must read documents that were shared with you but not created by md-gdoc, which the narrower `drive.file` scope does not allow. The tokens live only in `~/.config/md-gdoc/` on your machine, and the tool only ever touches the documents you name. If that scope is broader than you're comfortable with, use a dedicated Google account.

## Commands

### `md-gdoc push <file> [--replace] [--force] [--yes]`

First push creates a Google Doc titled after the filename and writes `gdoc_id`/`gdoc_url` into the file's frontmatter. Later pushes diff your changes block-by-block and edit only the changed ranges, so comment anchors on untouched text survive. If a push would orphan comments, it tells you and asks first.

- `--replace` — wipe the doc and re-import from scratch (orphans **all** comment anchors). Also the escape hatch when the diff path can't handle a change (images, footnotes).
- `--force` — push even though the remote doc has changes you haven't pulled.
- `--yes` — skip confirmation prompts (for scripts and agents).

### `md-gdoc pull <file>`

Fetches all comment threads (with quoted anchor text, replies, and resolved/open state) into `<file>.comments.md`, and reconciles remote edits:

- Remote unchanged → nothing to do.
- Remote changed, local unchanged → remote edits are applied to your file.
- Both changed → the remote version is written to `<file>.remote.md` and you (or your agent) merge manually, then push.

### `md-gdoc status <file>`

One cheap check: are there remote edits or open comments waiting?

### `md-gdoc clone <url-or-id> [file-or-directory]`

Start from an existing Google Doc instead: creates a bound local markdown file (named from the doc title unless you pass a path), saves its comments, and sets up sync state. Docs with multiple tabs become one file per tab plus a shared comments file.

## How it works

- **Binding** lives in the markdown file's YAML frontmatter: `gdoc_id`, `gdoc_url`, and for tabbed docs `tab_id` and `comments_file`. Your other frontmatter keys are never touched.
- **Sync state** lives in a `.sync/` directory next to the file: the local body and Google's export of it at the last successful push/pull. These snapshots are the merge base that lets md-gdoc distinguish your edits from your reviewers'.
- **Content is built with the Docs API** (`batchUpdate`), not Drive's markdown import, which mangles code blocks. Code blocks round-trip byte-perfectly, including the language tag.
- **Images come out of the doc as files.** Google's export embeds images as base64 data URIs; `pull` and `clone` extract them into `<name>.assets/` next to the file (named by content hash, so pulls are stable) and link them relatively. Pushing images back into a doc isn't supported — the Docs API only accepts publicly-accessible image URLs ([#3](https://github.com/MattFisher/md-gdoc/issues/3)).

Add to the `.gitignore` of repos where you use md-gdoc:

```gitignore
.sync/
*.comments.md
*.remote.md
```

### Markdown support

| Feature                 | Push                | Round-trip                              |
| ----------------------- | ------------------- | --------------------------------------- |
| Headings, paragraphs    | ✅                  | ✅                                      |
| Bold, italic, links     | ✅                  | ✅                                      |
| Inline code             | ✅                  | ✅                                      |
| Fenced code blocks      | ✅                  | ✅ byte-perfect                         |
| Lists (nested, ordered) | ✅                  | ✅                                      |
| Block quotes            | ✅                  | ✅                                      |
| Tables                  | ✅                  | ✅                                      |
| Images                  | ❌ dropped on push  | ⬇️ pull-only: saved to `<name>.assets/` |
| Footnotes               | ⚠️ `--replace` only | ❌                                      |

### Known limitations (alpha)

- Comments are read-only: you can't reply to or resolve threads from the local side yet (comment IDs are retained, so this can come later).
- Google Docs "suggestion mode" edits are invisible until a reviewer accepts them; accepted suggestions flow through `pull` normally.
- Comment anchors are orphaned when the anchored text itself changes — that's how Docs works; md-gdoc warns you before it happens.
- The Python modules are not a stable library API; only the CLI is the supported interface for now.

## Development

```bash
uv sync                     # install with dev dependencies
uv run pytest               # unit tests (no network, fake API)
uv run ruff check .         # lint
```

The end-to-end suite exercises the real Docs/Drive APIs against disposable documents. It is opt-in because it needs your OAuth credentials:

```bash
RUN_MD_GDOC_E2E=1 uv run pytest tests/e2e -q
```

It creates and deletes real docs in a Drive folder named `md-gdoc-e2e` (override with `MD_GDOC_E2E_FOLDER`). Regenerate the golden export with `RUN_MD_GDOC_E2E=1 python -m tests.e2e.test_end_to_end --generate`.

Design history: [design spec](docs/superpowers/specs/2026-07-02-gdoc-sync-design.md) and [implementation plan](docs/superpowers/plans/2026-07-02-gdoc-sync.md) (written under the tool's original name, gdoc-sync).

## License

[MIT](LICENSE)
