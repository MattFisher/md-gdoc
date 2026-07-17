"""Translate markdown blocks into Docs API batchUpdate requests."""

import re as _re
from dataclasses import dataclass, replace
from typing import Any

from markdown_it import MarkdownIt

from md_gdoc.mdblocks import Block

_md = MarkdownIt("commonmark")

_MARKER = {
    "heading": _re.compile(r"^#{1,6}\s+"),
    "list_item": _re.compile(r"^\s*([-*+]|\d+[.)])\s+"),
}


def _loc(index, tab_id=None):
    d = {"index": index}
    if tab_id:
        d["tabId"] = tab_id
    return {"location": d}


def _rng(start, end, tab_id=None):
    d = {"startIndex": start, "endIndex": end}
    if tab_id:
        d["tabId"] = tab_id
    return d


@dataclass(frozen=True)
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    link: str | None = None
    code: bool = False


# Docs' code-font family (Fira Code, like Roboto Mono which Drive's own
# markdown import uses, but per Matt's preference). Exporting text in a code
# font re-emits `backticks` around it, so inline code round-trips without
# literal backtick characters in the doc; the color matches Drive's import.
_CODE_FONT = {"fontFamily": "Fira Code"}
_CODE_COLOR = {"color": {"rgbColor": {"red": 0.09411765, "green": 0.5019608, "blue": 0.21960784}}}


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
            href = tok.attrs.get("href")
            link = str(href) if href is not None else None
        elif tok.type == "link_close":
            link = None
        elif tok.type == "code_inline":
            runs.append(Run(tok.content, bold > 0, italic > 0, link, code=True))
        elif tok.type in ("softbreak", "hardbreak"):
            runs.append(Run(" ", bold > 0, italic > 0, link))
        elif tok.type == "text" and tok.content:
            runs.append(Run(tok.content, bold > 0, italic > 0, link))
    return _merge(runs)


def _merge(runs):
    out: list[Run] = []
    for r in runs:
        if out and (
            (out[-1].bold, out[-1].italic, out[-1].link, out[-1].code)
            == (r.bold, r.italic, r.link, r.code)
        ):
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
        return " ".join([head] + [line.strip() for line in lines[1:]])
    if block.kind == "quote":
        return "\n".join(_re.sub(r"^\s*>\s?", "", line) for line in block.source.split("\n"))
    return block.source


def _code_requests(block, index, tab_id=None):
    # Store as one paragraph with soft line breaks (\v) between lines so the
    # whole block is a single doc paragraph (keeps docmodel alignment 1:1).
    # \r is NOT accepted by the Docs API as a line break (it gets dropped,
    # shifting all indices). Because the paragraph is in a code font, export
    # wraps each line in an inline code span; unescape._extract_code_regions
    # decodes that back into a fenced block.
    # AUTHORITY: the e2e round-trip test (tests/e2e) validates this encoding
    # against the live API. If e2e disagrees, fix this function, not e2e.
    text = block.source.rstrip("\n").replace("\n", "\v") + "\n"
    rng = _rng(index, index + len(text), tab_id)
    return [
        {"insertText": {**_loc(index, tab_id), "text": text}},
        # Paragraph style first: applying namedStyleType resets character
        # styles, so the font must come after it.
        {
            "updateParagraphStyle": {
                "range": rng,
                "paragraphStyle": {
                    "namedStyleType": "NORMAL_TEXT",
                    # Code blocks are single paragraphs, so without spacing
                    # adjacent blocks (and surrounding text) render flush.
                    "spaceAbove": {"magnitude": 6, "unit": "PT"},
                    "spaceBelow": {"magnitude": 6, "unit": "PT"},
                },
                "fields": "namedStyleType,spaceAbove,spaceBelow",
            }
        },
        {
            "updateTextStyle": {
                "range": rng,
                "textStyle": {"weightedFontFamily": _CODE_FONT},
                "fields": "weightedFontFamily",
            }
        },
    ]


def _style_requests(runs, offset, tab_id=None):
    reqs = []
    for r in runs:
        end = offset + len(r.text)
        style: dict[str, Any] = {}
        fields: list[str] = []
        if r.bold:
            style["bold"] = True
            fields.append("bold")
        if r.italic:
            style["italic"] = True
            fields.append("italic")
        if r.link:
            style["link"] = {"url": r.link}
            fields.append("link")
        if r.code:
            style["weightedFontFamily"] = _CODE_FONT
            style["foregroundColor"] = _CODE_COLOR
            fields += ["weightedFontFamily", "foregroundColor"]
        if fields:
            reqs.append(
                {
                    "updateTextStyle": {
                        "range": _rng(offset, end, tab_id),
                        "textStyle": style,
                        "fields": ",".join(fields),
                    }
                }
            )
        offset = end
    return reqs


def list_requests(blocks, index, tab_id=None):
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
        style_reqs += _style_requests(runs, offset + len(prefix), tab_id)
        offset += len(texts[-1])
    full = "".join(texts)
    preset = "NUMBERED_DECIMAL_ALPHA_ROMAN" if blocks[0].ordered else "BULLET_DISC_CIRCLE_SQUARE"
    run_rng = _rng(index, index + len(full), tab_id)
    return [
        {"insertText": {**_loc(index, tab_id), "text": full}},
        # Reset any inherited heading style before applying bullets.
        {
            "updateParagraphStyle": {
                "range": run_rng,
                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                "fields": "namedStyleType",
            }
        },
        *style_reqs,
        # Last: createParagraphBullets consumes the leading tabs, shifting
        # indices, so every index-addressed request must come before it.
        {
            "createParagraphBullets": {
                "range": run_rng,
                "bulletPreset": preset,
            }
        },
    ]


def segment_blocks(blocks: list[Block]) -> list[list[Block]]:
    """Split blocks into runs of consecutive same-ordered-ness list_items.

    Such items must be inserted together (see list_requests); every other block
    is a run of one.
    """
    runs: list[list[Block]] = []
    for b in blocks:
        if (
            b.kind == "list_item"
            and runs
            and runs[-1][0].kind == "list_item"
            and runs[-1][0].ordered == b.ordered
        ):
            runs[-1].append(b)
        else:
            runs.append([b])
    return runs


def run_requests(run, index, tab_id=None):
    """Requests for one segment_blocks() run."""
    if run[0].kind == "list_item":
        return list_requests(run, index, tab_id)
    return block_requests(run[0], index, tab_id)


def block_requests(block, index, tab_id=None):
    if block.kind == "table":
        return table_requests(block, index, tab_id)
    if block.kind == "code":
        return _code_requests(block, index, tab_id)
    if block.kind == "list_item":
        return list_requests([block], index, tab_id)
    runs = inline_runs(content_text(block).replace("\n", " "))
    text = "".join(r.text for r in runs) + "\n"
    reqs = [{"insertText": {**_loc(index, tab_id), "text": text}}]

    rng = _rng(index, index + len(text), tab_id)
    # Named paragraph styles must be applied BEFORE character styles: applying
    # a namedStyleType resets bold/italic/links on the range.
    if block.kind == "quote":
        reqs.append(
            {
                "updateParagraphStyle": {
                    "range": rng,
                    "paragraphStyle": {
                        "namedStyleType": "NORMAL_TEXT",
                        "indentStart": {"magnitude": 36, "unit": "PT"},
                        "indentFirstLine": {"magnitude": 36, "unit": "PT"},
                    },
                    "fields": "namedStyleType,indentStart,indentFirstLine",
                }
            }
        )
    else:
        named = f"HEADING_{block.level}" if block.kind == "heading" else "NORMAL_TEXT"
        reqs.append(
            {
                "updateParagraphStyle": {
                    "range": rng,
                    "paragraphStyle": {"namedStyleType": named},
                    "fields": "namedStyleType",
                }
            }
        )

    return reqs + _style_requests(runs, index, tab_id)


def parse_table(source):
    rows = []
    for i, line in enumerate(source.split("\n")):
        if i == 1:
            continue  # separator row
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def _cell_index(index, r, c, cols):
    # Empty-table layout: +1 table element, then per row +1, per cell +2
    # (cell start + empty paragraph). First cell paragraph sits at index+4.
    # AUTHORITY: the e2e round-trip test (tests/e2e) validates this against
    # the live API. If e2e disagrees, fix this function, not e2e.
    return index + 4 + r * (2 * cols + 1) + 2 * c


def table_requests(block, index, tab_id=None):
    rows = parse_table(block.source)
    n_rows, n_cols = len(rows), len(rows[0])
    reqs = [{"insertTable": {**_loc(index, tab_id), "rows": n_rows, "columns": n_cols}}]
    for r in range(n_rows - 1, -1, -1):  # reverse: highest index first
        for c in range(n_cols - 1, -1, -1):
            cell_md = rows[r][c]
            if not cell_md:
                continue
            runs = inline_runs(cell_md)
            text = "".join(x.text for x in runs)
            at = _cell_index(index, r, c, n_cols)
            reqs.append({"insertText": {**_loc(at, tab_id), "text": text}})
            reqs += _style_requests(runs, at, tab_id)
    return reqs
