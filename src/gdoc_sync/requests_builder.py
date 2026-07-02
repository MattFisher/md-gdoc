"""Translate markdown blocks into Docs API batchUpdate requests."""

from dataclasses import dataclass, replace

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark")


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
