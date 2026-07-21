"""Clean Google Docs markdown export output."""

import re

from markdown_it import MarkdownIt

_ESCAPED = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~\"'])")
_BLANKS = re.compile(r"\n{3,}")
_SPAN_LINE = re.compile(r"^(\s*)(`+.*`+)\s*$")
_md = MarkdownIt("commonmark")


def _span_content(line: str) -> tuple[str, str] | None:
    """Return (indent, content) if line is exactly one inline code span."""
    m = _SPAN_LINE.match(line)
    if not m:
        return None
    tokens = _md.parseInline(m.group(2))[0].children or []
    if len(tokens) == 1 and tokens[0].type == "code_inline":
        return m.group(1), tokens[0].content
    return None


def _extract_code_regions(md: str) -> tuple[str, list[str]]:
    """Decode span-encoded code blocks into placeholders; return (md, stash).

    Code-block paragraphs are stored in a code font, so Google's export wraps
    each line in an inline code span (with CommonMark multi-backtick
    delimiters when the code itself contains backticks). A full-line span
    whose content starts with ``` opens a block; a bare ``` span closes it.
    Extraction happens BEFORE the un-escape pass so code content — which the
    exporter emits raw inside spans — stays byte-exact.
    """
    lines = md.split("\n")
    out: list[str] = []
    stash: list[str] = []
    region: list[str] | None = None
    for line in lines:
        sc = _span_content(line)
        if region is None:
            if sc and sc[1].startswith("```"):
                region = [sc[1]]
            else:
                out.append(line)
        elif sc and sc[1] == "```":
            region.append("```")
            out += ["", f"\x00{len(stash)}\x00", ""]
            stash.append("\n".join(region))
            region = None
        elif sc:
            region.append(sc[0] + sc[1])
        else:
            region.append(line.rstrip())
    if region is not None:  # unterminated: emit as-is
        out += region
    return "\n".join(out), stash


def _restore_code_regions(md: str, stash: list[str]) -> str:
    for i, block in enumerate(stash):
        md = md.replace(f"\x00{i}\x00", block)
    return md


def _clean_code_blocks(md: str) -> str:
    r"""Strip trailing whitespace within legacy escaped-fence code blocks.

    Docs pushed before the code-font change exported code blocks as escaped
    \\`\\`\\` fence lines with hard-break trailing spaces; keep decoding them
    so pulls from older docs still reconstruct valid fenced markdown.
    """
    lines, result, in_fence = md.split("\n"), [], False
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped.startswith(("```", "~~~")):
            closing = in_fence
            in_fence = not in_fence
            result.append(stripped)
            # Google exports adjacent paragraphs with a hard break instead of
            # a blank line; restore the blank line after a closing fence so
            # back-to-back code blocks don't fuse in the pulled markdown.
            if closing and i + 1 < len(lines) and lines[i + 1].strip():
                result.append("")
        elif in_fence:
            result.append(stripped)
        else:
            result.append(line)
    return "\n".join(result)


def clean(md: str) -> str:
    md = md.replace("\r\n", "\n")
    md, stash = _extract_code_regions(md)
    md = _ESCAPED.sub(r"\1", md)
    md = _clean_code_blocks(md)
    md = _BLANKS.sub("\n\n", md)
    md = _restore_code_regions(md, stash)
    return md.strip("\n") + "\n"
