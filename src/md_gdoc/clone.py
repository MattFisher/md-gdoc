"""Clone: create a local markdown file from an existing Google Doc."""

import re
from dataclasses import dataclass
from pathlib import Path

from . import snapshot
from .api import _split_by_tabs
from .comments import from_api, render
from .pull import _fmt
from .unescape import clean

_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def _extract_doc_id(url_or_id: str) -> str:
    m = _DOC_ID_RE.search(url_or_id)
    if m:
        return m.group(1)
    # Bare ID: no slashes, looks like a Google Doc ID
    if re.fullmatch(r"[a-zA-Z0-9_-]+", url_or_id):
        return url_or_id
    raise SystemExit(
        f"Cannot parse a Google Doc ID from {url_or_id!r}.\n"
        "Pass the full document URL or the bare document ID."
    )


def _title_to_filename(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return (slug or "document") + ".md"


def _tab_filename(doc_title: str, tab_title: str) -> str:
    return _title_to_filename(doc_title)[:-3] + "--" + _title_to_filename(tab_title)


@dataclass
class CloneResult:
    path: Path
    comment_count: int
    url: str


def clone(url_or_id: str, out_path: str | None, api) -> "CloneResult | list[CloneResult]":
    doc_id = _extract_doc_id(url_or_id)
    url = api.doc_url(doc_id)

    doc = api.get_document(doc_id)
    title = doc.get("title", "Untitled")
    tabs = api.list_tabs(doc_id)

    # Resolve out_path as a directory if it is one (or ends with /)
    out_dir: Path | None = None
    if out_path is not None:
        p = Path(out_path)
        if p.is_dir() or out_path.endswith("/"):
            out_dir = p
            out_path = None

    if tabs:
        # Multi-file: one file per tab
        if out_path is not None:
            raise SystemExit(
                "This document has multiple tabs. Pass a directory (or omit the argument) — "
                "md-gdoc will create one file per tab."
            )
        base_dir = out_dir or Path(".")
        base_dir.mkdir(parents=True, exist_ok=True)
        results = []
        full_md = api.export_markdown(doc_id)
        split = _split_by_tabs(full_md, tabs)
        threads = from_api(api.list_comments(doc_id))
        # One shared comments file for the whole doc (comments aren't tab-scoped)
        shared_comments_name = _title_to_filename(title) + ".comments.md"
        shared_comments_path = base_dir / shared_comments_name
        # Use first tab's filename as the anchor for rendering comment links
        first_fname = _tab_filename(doc_title=title, tab_title=tabs[0]["title"])
        shared_comments_path.write_text(render(threads, first_fname), encoding="utf-8")
        for tab in tabs:
            tab_body = clean(split.get(tab["id"], "\n"))
            body = _fmt(tab_body)
            fname = _tab_filename(doc_title=title, tab_title=tab["title"])
            md_path = base_dir / fname
            if md_path.exists():
                raise SystemExit(f"{md_path} already exists.")
            text = (
                f"---\ngdoc_id: {doc_id}\ngdoc_url: {url}\n"
                f"tab_id: {tab['id']}\ncomments_file: {shared_comments_name}\n---\n{body}"
            )
            md_path.write_text(text, encoding="utf-8")
            snapshot.save(md_path, body)
            snapshot.save_remote(md_path, tab_body)
            results.append(CloneResult(path=md_path, comment_count=len(threads), url=url))
        return results

    # Single file: existing behavior
    remote_raw = api.export_markdown(doc_id)
    remote_body = clean(remote_raw)
    body = _fmt(remote_body)

    threads = from_api(api.list_comments(doc_id))

    fname = out_path or _title_to_filename(title)
    md_path = (out_dir / fname) if out_dir else Path(fname)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    if md_path.exists():
        raise SystemExit(f"{md_path} already exists — remove it first or pass a different path.")

    text = f"---\ngdoc_id: {doc_id}\ngdoc_url: {url}\n---\n{body}"
    md_path.write_text(text, encoding="utf-8")

    snapshot.save(md_path, body)
    snapshot.save_remote(md_path, remote_body)

    comments_path = md_path.parent / (md_path.name + ".comments.md")
    comments_path.write_text(render(threads, md_path.name), encoding="utf-8")

    return CloneResult(path=md_path, comment_count=len(threads), url=url)
