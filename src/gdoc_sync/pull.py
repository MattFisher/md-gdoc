"""Pull: export remote content, fetch comments, reconcile with local file."""

from dataclasses import dataclass
from pathlib import Path

from . import binding, snapshot
from .comments import from_api, render
from .unescape import clean


@dataclass
class PullResult:
    state: str
    comment_count: int
    remote_path: Path | None = None


def pull(md_path, api):
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    doc_id, _, local_body = binding.read(text)
    if not doc_id:
        raise SystemExit(
            f"{md_path} has no gdoc_id in frontmatter — push it first."
        )

    remote_body = clean(api.export_markdown(doc_id))
    threads = from_api(api.list_comments(doc_id))
    comments_path = md_path.parent / (md_path.name + ".comments.md")
    comments_path.write_text(render(threads, md_path.name), encoding="utf-8")

    base = snapshot.load(md_path)
    local_clean = clean(local_body)

    if remote_body == (clean(base) if base is not None else local_clean):
        if base is None:
            snapshot.save(md_path, remote_body)
        return PullResult("clean", len(threads))

    if base is not None and local_clean == clean(base):
        md_path.write_text(binding.replace_body(text, remote_body), encoding="utf-8")
        snapshot.save(md_path, remote_body)
        return PullResult("updated", len(threads))

    remote_path = md_path.parent / (md_path.name + ".remote.md")
    remote_path.write_text(remote_body, encoding="utf-8")
    return PullResult("conflict", len(threads), remote_path)
