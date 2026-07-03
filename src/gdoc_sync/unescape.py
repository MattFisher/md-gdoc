"""Clean Google Docs markdown export output."""

import re

_ESCAPED = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~\"'])")
_BLANKS = re.compile(r"\n{3,}")


def _clean_code_blocks(md):
    """Strip trailing whitespace from lines within fenced code blocks.

    Google Docs exports soft line breaks (\\v) as trailing spaces. Code blocks
    are stored with \\v separators so they arrive here with spurious trailing
    spaces on every line that must be removed to produce valid fenced markdown.
    """
    lines, result, in_fence = md.split("\n"), [], False
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            result.append(stripped)
        elif in_fence:
            result.append(stripped)
        else:
            result.append(line)
    return "\n".join(result)


def clean(md):
    md = md.replace("\r\n", "\n")
    md = _ESCAPED.sub(r"\1", md)
    md = _clean_code_blocks(md)
    md = _BLANKS.sub("\n\n", md)
    return md.rstrip("\n") + "\n"
