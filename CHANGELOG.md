# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `push` crashed with an IndexError (or refused tables) when the bound doc
  was empty — e.g. after cloning a blank doc and then writing content
  locally. An empty doc is now populated via the first-push insertion path.

### Added

- `pull` and `clone` extract images from the doc into files instead of
  leaving them as base64 data URIs (which made pulled files enormous).
  Images are written next to the markdown file in `<name>.assets/`, named
  by content hash so repeated pulls are stable and duplicates are stored
  once, and referenced with relative links. The raw export (with data
  URIs) is still what's stored in the `.sync/` remote snapshot, so change
  detection is unaffected. Pushing images into a doc remains unsupported
  (#3).

## [0.1.0] - 2026-07-14

First public release (alpha). Previously developed as `gdoc-sync`.

### Added

- `md-gdoc push` — create a Google Doc from a markdown file on first push;
  block-level diffing on later pushes edits only changed ranges so comment
  anchors on untouched text survive. `--replace` for full re-import,
  `--force` to override the remote-changes guard, `--yes` for
  non-interactive use.
- `md-gdoc pull` — fetch comment threads (anchors, replies, resolved state)
  into `<file>.comments.md`; apply remote edits to the local file when it is
  otherwise unchanged, or write `<file>.remote.md` on conflict.
- `md-gdoc status` — report pending remote edits and open comment count.
- `md-gdoc clone` — bootstrap a bound local markdown file from an existing
  Google Doc; multi-tab docs become one file per tab with a shared comments
  file.
- Frontmatter binding (`gdoc_id`, `gdoc_url`, `tab_id`, `comments_file`) and
  `.sync/` snapshots as the three-way merge base.
- Byte-perfect code block round-trip (single-paragraph code-font encoding;
  Drive markdown import is not used).
- OAuth installed-app flow with cached token (`~/.config/md-gdoc/`),
  exponential backoff on Docs API rate limits.

[Unreleased]: https://github.com/MattFisher/md-gdoc/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MattFisher/md-gdoc/releases/tag/v0.1.0
