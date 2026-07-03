"""Push: first-push block insertion, anchor-preserving revision diff, --replace."""

from dataclasses import dataclass, field
from pathlib import Path

from . import binding, snapshot
from .diffing import diff_blocks
from .docmodel import AlignmentError, check_alignment, doc_blocks
from .mdblocks import parse_blocks, unsupported
from .requests_builder import run_requests, segment_blocks
from .unescape import clean


@dataclass
class PushResult:
    state: str
    url: str = ""
    orphaned: list = field(default_factory=list)


def push(md_path, api, replace=False, force=False, yes=False, confirm=input):
    md_path = Path(md_path)
    text = md_path.read_text(encoding="utf-8")
    doc_id, url, body = binding.read(text)

    if not doc_id:
        blocks = parse_blocks(body)
        doc_id, url = api.create_doc(md_path.stem)
        _insert_blocks(doc_id, blocks, api)
        md_path.write_text(binding.bind(text, doc_id, url), encoding="utf-8")
        remote = clean(api.export_markdown(doc_id))
        snapshot.save(md_path, body)
        snapshot.save_remote(md_path, remote)
        return PushResult("created", url)

    if replace:
        if not yes and confirm(
            "--replace rewrites the whole doc and orphans ALL comment "
            "anchors. Continue? [y/N] "
        ).strip().lower() not in ("y", "yes"):
            raise SystemExit("aborted")
        _clear_doc(doc_id, api)
        _insert_blocks(doc_id, parse_blocks(body), api)
        remote = clean(api.export_markdown(doc_id))
        snapshot.save(md_path, body)
        snapshot.save_remote(md_path, remote)
        return PushResult("replaced", url)

    base = snapshot.load(md_path)
    if base is None:
        raise SystemExit(
            f"No snapshot for {md_path.name} (fresh clone?). Run pull first, "
            "or push --replace."
        )

    base_remote = snapshot.load_remote(md_path)
    expected_remote = base_remote if base_remote is not None else clean(base)
    if clean(api.export_markdown(doc_id)) != expected_remote and not force:
        raise SystemExit("remote has changes — run pull first (or --force)")

    base_blocks, new_blocks = parse_blocks(base), parse_blocks(body)
    ops = diff_blocks(base_blocks, new_blocks)
    if all(o.op == "equal" for o in ops):
        return PushResult("noop", url)

    touched = [
        b
        for o in ops
        if o.op != "equal"
        for b in (base_blocks[o.old[0] : o.old[1]] + new_blocks[o.new[0] : o.new[1]])
        if b.kind == "other"
    ]
    if touched:
        names = "; ".join(unsupported(touched))
        raise SystemExit(
            f"Changed blocks the diff path can't handle ({names}). "
            "Use push --replace."
        )

    doc = doc_blocks(api.get_document(doc_id))
    try:
        check_alignment(doc, base_blocks)
    except AlignmentError as e:
        raise SystemExit(f"Doc/snapshot mismatch: {e.detail}") from e

    orphaned = _orphaned_comments(api.list_comments(doc_id), ops, base_blocks)
    if orphaned and not yes:
        answer = confirm(
            f"This push will orphan {len(orphaned)} comment(s). Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            raise SystemExit("aborted")

    requests = []
    for op in reversed(ops):
        if op.op == "equal":
            continue
        if op.old[0] < op.old[1]:                    # delete or replace: remove old range
            start = doc[op.old[0]].start
            end = doc[op.old[1] - 1].end
            # NOTE: if op.old[1] == len(doc), the range covers the final paragraph which
            # includes the doc's terminating newline. If the live API returns 400, clamp
            # end to end-1 and insert with a leading "\n" instead.
            insert_at = start
            requests.append(
                {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}
            )
        else:                                        # pure insert
            i = op.old[0]
            insert_at = doc[i].start if i < len(doc) else doc[-1].end
        new_range = new_blocks[op.new[0] : op.new[1]]
        if len(new_range) > 1:
            for blk in new_range:
                if blk.kind == "table":
                    raise SystemExit(
                        f"Cannot insert table block alongside sibling blocks in one op "
                        f"({blk.source.splitlines()[0][:60]!r}). "
                        "Use push --replace."
                    )
        for run in reversed(segment_blocks(new_range)):
            requests += run_requests(run, insert_at)

    api.batch_update(doc_id, requests)
    remote = clean(api.export_markdown(doc_id))
    snapshot.save(md_path, body)
    snapshot.save_remote(md_path, remote)
    return PushResult("pushed", url, orphaned)


def _insert_blocks(doc_id, blocks, api):
    """Populate a blank doc with blocks, inserting one run per batchUpdate
    (consecutive list items form one run so their nesting survives).

    Before each insertion, fetches the document to find the startIndex of the
    trailing empty paragraph (the blank doc's original \\n). Pre-computing
    cumulative offsets is fragile due to Google's internal document structure;
    re-fetching is slower but always correct.
    """
    for run in segment_blocks(blocks):
        content = api.get_document(doc_id)["body"]["content"]
        index = _trailing_para_index(content)
        api.batch_update(doc_id, run_requests(run, index))


def _clear_doc(doc_id, api):
    """Delete all body content, leaving the doc's final empty paragraph."""
    content = api.get_document(doc_id)["body"]["content"]
    end = content[-1]["endIndex"]
    if end > 2:  # a blank doc ends at index 2; nothing to delete below that
        api.batch_update(doc_id, [
            {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end - 1}}}
        ])


def _trailing_para_index(content):
    """Return the startIndex of the last non-table, non-sectionBreak element."""
    for el in reversed(content):
        if "sectionBreak" not in el and "table" not in el:
            return el["startIndex"]
    return 1


def _orphaned_comments(comment_items, ops, base_blocks):
    changed_text = "\n\n".join(
        b.source for o in ops if o.op in ("replace", "delete")
        for b in base_blocks[o.old[0] : o.old[1]]
    )
    out = []
    for it in comment_items:
        if it.get("resolved") or it.get("deleted"):
            continue
        quoted = (it.get("quotedFileContent") or {}).get("value")
        if quoted and quoted in changed_text:
            out.append(quoted)
    return out
