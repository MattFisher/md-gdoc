"""Translate markdown blocks into Docs API batchUpdate requests."""

import re as _re
from dataclasses import dataclass, replace

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark")

_MARKER = {"heading": _re.compile(r"^#{1,6}\s+"), "list_item": _re.compile(r"^\s*([-*+]|\d+[.)])\s+")}


@dataclass(frozen=True)
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    link: str = None


def inline_runs(text):
    tokens = _md.parseInline(text)[0].children or []
    runs, bold, italic, link = [], 0, 0, None
    for tok in tokens:
        if tok.type == "strong_open":
            bold += 1
        elif tok.type == "strong_close":
            bold -= 1
        elif tok.type == "em_open":
            italic += 1
        elif tok.type == "em_close":
            italic -= 1
        elif tok.type == "link_open":
            link = tok.attrs.get("href")
        elif tok.type == "link_close":
            link = None
        elif tok.type == "code_inline":
            runs.append(Run(f"`{tok.content}`", bold > 0, italic > 0, link))
        elif tok.type in ("softbreak", "hardbreak"):
            runs.append(Run(" ", bold > 0, italic > 0, link))
        elif tok.type == "text" and tok.content:
            runs.append(Run(tok.content, bold > 0, italic > 0, link))
    return _merge(runs)


def _merge(runs):
    out = []
    for r in runs:
        if out and (out[-1].bold, out[-1].italic, out[-1].link) == (r.bold, r.italic, r.link):
            out[-1] = replace(out[-1], text=out[-1].text + r.text)
        else:
            out.append(r)
    return out


def content_text(block):
    if block.kind == "heading":
        return _MARKER["heading"].sub("", block.source)
    if block.kind == "list_item":
        lines = block.source.split("\n")
        head = _MARKER["list_item"].sub("", lines[0])
        return " ".join([head] + [l.strip() for l in lines[1:]])
    if block.kind == "quote":
        return "\n".join(_re.sub(r"^\s*>\s?", "", l) for l in block.source.split("\n"))
    return block.source


def _code_requests(block, index):
    # Store as one paragraph with soft line breaks (\v) between lines so the
    # whole block is a single doc paragraph (keeps docmodel alignment 1:1) and
    # Google exports it without blank-line separation. \r is NOT accepted by
    # the Docs API as a line break (it gets dropped, shifting all indices).
    # AUTHORITY: the e2e round-trip test (tests/e2e) validates this encoding
    # against the live API. If e2e disagrees, fix this function, not e2e.
    text = block.source.rstrip("\n").replace("\n", "\v") + "\n"
    rng = {"startIndex": index, "endIndex": index + len(text)}
    return [
        {"insertText": {"location": {"index": index}, "text": text}},
        # Paragraph style first: applying namedStyleType resets character
        # styles, so Courier must come after it.
        {
            "updateParagraphStyle": {
                "range": rng,
                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                "fields": "namedStyleType",
            }
        },
        {
            "updateTextStyle": {
                "range": rng,
                "textStyle": {"weightedFontFamily": {"fontFamily": "Courier New"}},
                "fields": "weightedFontFamily",
            }
        },
    ]


def _style_requests(runs, offset):
    reqs = []
    for r in runs:
        end = offset + len(r.text)
        style, fields = {}, []
        if r.bold:
            style["bold"] = True
            fields.append("bold")
        if r.italic:
            style["italic"] = True
            fields.append("italic")
        if r.link:
            style["link"] = {"url": r.link}
            fields.append("link")
        if fields:
            reqs.append({
                "updateTextStyle": {
                    "range": {"startIndex": offset, "endIndex": end},
                    "textStyle": style,
                    "fields": ",".join(fields),
                }
            })
        offset = end
    return reqs


def list_requests(blocks, index):
    """Requests for a run of consecutive list_item blocks (same ordered-ness).

    The whole run gets ONE insertText and ONE createParagraphBullets: applying
    bullets per item resets tab-derived nesting to level 0 (live-API behaviour),
    so nested items only survive when the run is inserted as a unit.
    """
    texts, style_reqs, offset = [], [], index
    for block in blocks:
        runs = inline_runs(content_text(block).replace("\n", " "))
        prefix = "\t" * block.level
        texts.append(prefix + "".join(r.text for r in runs) + "\n")
        style_reqs += _style_requests(runs, offset + len(prefix))
        offset += len(texts[-1])
    full = "".join(texts)
    preset = "NUMBERED_DECIMAL_ALPHA_ROMAN" if blocks[0].ordered else "BULLET_DISC_CIRCLE_SQUARE"
    return [
        {"insertText": {"location": {"index": index}, "text": full}},
        *style_reqs,
        # Last: createParagraphBullets consumes the leading tabs, shifting
        # indices, so every index-addressed request must come before it.
        {"createParagraphBullets": {
            "range": {"startIndex": index, "endIndex": index + len(full)},
            "bulletPreset": preset,
        }},
    ]


def segment_blocks(blocks):
    """Split blocks into runs: consecutive list_items with the same ordered-ness
    form one run (they must be inserted together — see list_requests); every
    other block is a run of one."""
    runs = []
    for b in blocks:
        if (
            b.kind == "list_item" and runs
            and runs[-1][0].kind == "list_item" and runs[-1][0].ordered == b.ordered
        ):
            runs[-1].append(b)
        else:
            runs.append([b])
    return runs


def run_requests(run, index):
    """Requests for one segment_blocks() run."""
    if run[0].kind == "list_item":
        return list_requests(run, index)
    return block_requests(run[0], index)


def block_requests(block, index):
    if block.kind == "table":
        return table_requests(block, index)
    if block.kind == "code":
        return _code_requests(block, index)
    if block.kind == "list_item":
        return list_requests([block], index)
    runs = inline_runs(content_text(block).replace("\n", " "))
    text = "".join(r.text for r in runs) + "\n"
    reqs = [{"insertText": {"location": {"index": index}, "text": text}}]

    rng = {"startIndex": index, "endIndex": index + len(text)}
    # Named paragraph styles must be applied BEFORE character styles: applying
    # a namedStyleType resets bold/italic/links on the range.
    if block.kind == "quote":
        reqs.append({
            "updateParagraphStyle": {
                "range": rng,
                "paragraphStyle": {
                    "namedStyleType": "NORMAL_TEXT",
                    "indentStart": {"magnitude": 36, "unit": "PT"},
                    "indentFirstLine": {"magnitude": 36, "unit": "PT"},
                },
                "fields": "namedStyleType,indentStart,indentFirstLine",
            }
        })
    else:
        named = f"HEADING_{block.level}" if block.kind == "heading" else "NORMAL_TEXT"
        reqs.append({
            "updateParagraphStyle": {
                "range": rng,
                "paragraphStyle": {"namedStyleType": named},
                "fields": "namedStyleType",
            }
        })

    return reqs + _style_requests(runs, index)


def parse_table(source):
    rows = []
    for i, line in enumerate(source.split("\n")):
        if i == 1:
            continue                              # separator row
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def _cell_index(index, r, c, cols):
    # Empty-table layout: +1 table element, then per row +1, per cell +2
    # (cell start + empty paragraph). First cell paragraph sits at index+4.
    # AUTHORITY: the e2e round-trip test (tests/e2e) validates this against
    # the live API. If e2e disagrees, fix this function, not e2e.
    return index + 4 + r * (2 * cols + 1) + 2 * c


def table_requests(block, index):
    rows = parse_table(block.source)
    n_rows, n_cols = len(rows), len(rows[0])
    reqs = [{"insertTable": {"location": {"index": index}, "rows": n_rows, "columns": n_cols}}]
    for r in range(n_rows - 1, -1, -1):           # reverse: highest index first
        for c in range(n_cols - 1, -1, -1):
            cell_md = rows[r][c]
            if not cell_md:
                continue
            runs = inline_runs(cell_md)
            text = "".join(x.text for x in runs)
            at = _cell_index(index, r, c, n_cols)
            reqs.append({"insertText": {"location": {"index": at}, "text": text}})
            offset = at
            for x in runs:
                end = offset + len(x.text)
                style, fields = {}, []
                if x.bold:
                    style["bold"] = True
                    fields.append("bold")
                if x.italic:
                    style["italic"] = True
                    fields.append("italic")
                if x.link:
                    style["link"] = {"url": x.link}
                    fields.append("link")
                if fields:
                    reqs.append({
                        "updateTextStyle": {
                            "range": {"startIndex": offset, "endIndex": end},
                            "textStyle": style,
                            "fields": ",".join(fields),
                        }
                    })
                offset = end
    return reqs
