"""Split markdown into diffable blocks."""

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_FOOTNOTE_DEF = re.compile(r"^\[\^[^\]]+\]:")
_IMAGE = re.compile(r"!\[")
_FENCE = re.compile(r"^(```|~~~)")


@dataclass(frozen=True)
class Block:
    kind: str
    source: str
    level: int = 0
    ordered: bool = False


def parse_blocks(md):
    lines = md.replace("\r\n", "\n").split("\n")
    blocks, i, n = [], 0, len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        line = lines[i]
        if _FENCE.match(line):                      # fenced code: scan to closing fence
            j = i + 1
            while j < n and not _FENCE.match(lines[j]):
                j += 1
            blocks.append(Block("code", "\n".join(lines[i : min(j + 1, n)])))
            i = j + 1
        elif _HEADING.match(line):
            blocks.append(Block("heading", line.rstrip(), level=len(_HEADING.match(line).group(1))))
            i += 1
        elif _LIST.match(line):
            i = _consume_list(lines, i, blocks)
        elif line.lstrip().startswith(">"):
            j = i
            while j < n and lines[j].lstrip().startswith(">"):
                j += 1
            blocks.append(Block("quote", "\n".join(line.rstrip() for line in lines[i:j])))
            i = j
        elif "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            j = i
            while j < n and lines[j].strip() and "|" in lines[j]:
                j += 1
            blocks.append(Block("table", "\n".join(line.rstrip() for line in lines[i:j])))
            i = j
        else:                                        # paragraph (or footnote def / image)
            j = i
            while j < n and lines[j].strip() and not _is_block_start(lines, j):
                j += 1
            source = "\n".join(line.rstrip() for line in lines[i:j])
            blocks.append(Block(_paragraph_kind(source), source))
            i = j
    return blocks


def _is_block_start(lines, j):
    line = lines[j]
    return bool(
        _HEADING.match(line) or _LIST.match(line) or _FENCE.match(line)
        or line.lstrip().startswith(">")
        or ("|" in line and j + 1 < len(lines) and _TABLE_SEP.match(lines[j + 1]))
    )


def _paragraph_kind(source):
    if _FOOTNOTE_DEF.match(source) or _IMAGE.search(source):
        return "other"
    return "paragraph"


def _consume_list(lines, i, blocks):
    n = len(lines)
    while i < n and lines[i].strip():
        m = _LIST.match(lines[i])
        if not m:
            break
        indent, marker = m.group(1), m.group(2)
        item_lines = [lines[i].rstrip()]
        j = i + 1
        while j < n and lines[j].strip() and not _LIST.match(lines[j]):
            item_lines.append(lines[j].rstrip())    # continuation lines
            j += 1
        blocks.append(
            Block(
                "list_item",
                "\n".join(item_lines),
                level=len(indent.expandtabs(4)) // 2,
                ordered=marker[0].isdigit(),
            )
        )
        i = j
    return i


def unsupported(blocks):
    out = []
    for b in blocks:
        if b.kind != "other":
            continue
        first = b.source.splitlines()[0][:60]
        label = "image" if _IMAGE.search(b.source) else (
            "footnote" if _FOOTNOTE_DEF.match(b.source) else "code fence"
        )
        out.append(f"{label}: {first!r}")
    return out
