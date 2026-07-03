"""Push: first-push import, anchor-preserving revision diff, --replace."""

from dataclasses import dataclass, field
from pathlib import Path

from . import binding, snapshot
from .diffing import diff_blocks
from .docmodel import AlignmentError, check_alignment, doc_blocks
from .mdblocks import parse_blocks, unsupported
from .requests_builder import block_requests
from .unescape import clean


@dataclass
class PushResult:
    state: str
    url: str = ""
    orphaned: list = field(default_factory=list)


def push(md_path, api, replace=False, force=False, yes=False, confirm=input):
    md_path = Path(md_path)
    text = md_path.read_text()
    doc_id, url, body = binding.read(text)

    if not doc_id:
        doc_id, url = api.create_doc_from_markdown(md_path.stem, body)
        md_path.write_text(binding.bind(text, doc_id, url))
        snapshot.save(md_path, body)
        return PushResult("created", url)

    if replace:
        if not yes and confirm(
            "--replace re-imports the whole doc and orphans ALL comment "
            "anchors. Continue? [y/N] "
        ).strip().lower() not in ("y", "yes"):
            raise SystemExit("aborted")
        api.replace_doc_from_markdown(doc_id, body)
        snapshot.save(md_path, body)
        return PushResult("replaced", url)

    base = snapshot.load(md_path)
    if base is None:
        raise SystemExit(
            f"No snapshot for {md_path.name} (fresh clone?). Run pull first, "
            "or push --replace."
        )

    if clean(api.export_markdown(doc_id)) != clean(base) and not force:
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
        for block in reversed(new_blocks[op.new[0] : op.new[1]]):
            requests += block_requests(block, insert_at)

    api.batch_update(doc_id, requests)
    snapshot.save(md_path, body)
    return PushResult("pushed", url, orphaned)


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
