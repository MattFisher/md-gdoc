"""Block-level diff between snapshot and current markdown."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from md_gdoc.mdblocks import Block


@dataclass(frozen=True)
class BlockOp:
    op: str
    old: tuple[int, int]
    new: tuple[int, int]


def diff_blocks(base: list[Block], new: list[Block]) -> list[BlockOp]:
    sm = SequenceMatcher(a=[b.source for b in base], b=[b.source for b in new], autojunk=False)
    return [BlockOp(tag, (i1, i2), (j1, j2)) for tag, i1, i2, j1, j2 in sm.get_opcodes()]
