"""Pull: export remote content, fetch comments, reconcile with local file."""

from dataclasses import dataclass
from pathlib import Path

import mdformat

from . import binding, snapshot
from .comments import from_api, render
from .unescape import clean


def _fmt(md):
    """Normalize pulled markdown to a stable local dialect.

    Google's export dialect (`*` bullets, trailing hard-break spaces,
    `:----` separators) would otherwise leak into local files on every
    pull that takes remote changes.
    """
    return mdformat.text(md, extensions={"gfm"})


@dataclass
class PullResult:
    state: str
    comment_count: int
    remote_path: Path | None = None


def pull(md_path, api):
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    doc_id, _, local_body = binding.read(text)
    tab_id = binding.tab_id(text)
    if not doc_id:
        raise SystemExit(
            f"{md_path} has no gdoc_id in frontmatter — push it first."
        )

    remote_body = clean(api.export_tab_markdown(doc_id, tab_id) if tab_id else api.export_markdown(doc_id))
    threads = from_api(api.list_comments(doc_id))
    shared_cf = binding.comments_file(text)
    comments_path = (md_path.parent / shared_cf) if shared_cf else (md_path.parent / (md_path.name + ".comments.md"))
    comments_path.write_text(render(threads, md_path.name), encoding="utf-8")

    base = snapshot.load(md_path)
    base_remote = snapshot.load_remote(md_path)
    local_clean = clean(local_body)

    # Remote-changed check: compare fresh export against what Google had at last push.
    # Fall back to local snapshot (old behaviour) when remote snapshot absent.
    expected_remote = base_remote if base_remote is not None else (clean(base) if base is not None else local_clean)
    if remote_body == expected_remote:
        if base is None or base_remote is None:
            snapshot.save(md_path, remote_body)
            snapshot.save_remote(md_path, remote_body)
        return PullResult("clean", len(threads))

    # Local-unchanged check: compare current local body against local snapshot.
    if base is not None and local_clean == clean(base):
        body_out = _fmt(remote_body)
        md_path.write_text(binding.replace_body(text, body_out), encoding="utf-8")
        snapshot.save(md_path, body_out)
        snapshot.save_remote(md_path, remote_body)
        return PullResult("updated", len(threads))

    remote_path = md_path.parent / (md_path.name + ".remote.md")
    remote_path.write_text(_fmt(remote_body), encoding="utf-8")
    return PullResult("conflict", len(threads), remote_path)
