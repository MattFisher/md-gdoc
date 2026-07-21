"""Map a documents.get response onto diffable block ranges."""

from dataclasses import dataclass
from typing import Any

from md_gdoc.mdblocks import Block


class AlignmentError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class DocBlock:
    start: int
    end: int
    kind: str
    text: str


def doc_blocks(document: dict[str, Any]) -> list[DocBlock]:
    out: list[DocBlock] = []
    for el in document.get("body", {}).get("content", []):
        if "paragraph" in el:
            text = "".join(
                e.get("textRun", {}).get("content", "") for e in el["paragraph"].get("elements", [])
            )
            if text == "\n":
                continue
            out.append(DocBlock(el["startIndex"], el["endIndex"], "paragraph", text))
        elif "table" in el:
            out.append(DocBlock(el["startIndex"], el["endIndex"], "table", ""))
    return out


def check_alignment(doc: list[DocBlock], md: list[Block]) -> None:
    if len(doc) != len(md):
        raise AlignmentError(
            f"doc has {len(doc)} blocks but markdown snapshot has {len(md)}; "
            "the diff path cannot proceed — pull first or push --replace"
        )
    for i, (d, m) in enumerate(zip(doc, md, strict=False)):
        if (d.kind == "table") != (m.kind == "table"):
            raise AlignmentError(
                f"block {i} is a {d.kind} in the doc but {m.kind} in markdown; "
                "pull first or push --replace"
            )
