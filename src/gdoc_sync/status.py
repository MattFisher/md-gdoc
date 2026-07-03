"""Status: is there feedback waiting?"""

from dataclasses import dataclass
from pathlib import Path

from . import binding, snapshot
from .unescape import clean


@dataclass
class StatusResult:
    url: str
    remote_changed: bool
    open_comments: int


def status(md_path, api):
    md_path = Path(md_path)
    doc_id, url, _ = binding.read(md_path.read_text())
    if not doc_id:
        raise SystemExit(f"{md_path} has no gdoc_id in frontmatter — push it first.")
    base = snapshot.load(md_path)
    remote = clean(api.export_markdown(doc_id))
    changed = base is None or remote != clean(base)
    open_comments = sum(
        1 for c in api.list_comments(doc_id)
        if not c.get("resolved") and not c.get("deleted")
    )
    return StatusResult(url or "", changed, open_comments)
