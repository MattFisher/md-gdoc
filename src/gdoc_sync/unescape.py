"""Clean Google Docs markdown export output."""

import re

_ESCAPED = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~\"'])")
_BLANKS = re.compile(r"\n{3,}")


def clean(md):
    md = md.replace("\r\n", "\n")
    md = _ESCAPED.sub(r"\1", md)
    md = _BLANKS.sub("\n\n", md)
    return md.rstrip("\n") + "\n"
