from gdoc_sync.diffing import BlockOp, diff_blocks
from gdoc_sync.mdblocks import parse_blocks

BASE = parse_blocks("# T\n\nPara one.\n\nPara two.\n\nPara three.\n")


def test_no_change():
    assert [o.op for o in diff_blocks(BASE, BASE)] == ["equal"]


def test_edit_one_paragraph():
    new = parse_blocks("# T\n\nPara one.\n\nPara 2 edited.\n\nPara three.\n")
    ops = diff_blocks(BASE, new)
    assert [o.op for o in ops] == ["equal", "replace", "equal"]
    assert ops[1].old == (2, 3) and ops[1].new == (2, 3)


def test_insert_and_delete():
    new = parse_blocks("# T\n\nPara one.\n\nInserted.\n\nPara two.\n\nPara three.\n")
    ops = diff_blocks(BASE, new)
    assert ("insert", (2, 2), (2, 3)) == (ops[1].op, ops[1].old, ops[1].new)

    new2 = parse_blocks("# T\n\nPara one.\n\nPara three.\n")
    ops2 = diff_blocks(BASE, new2)
    assert [o.op for o in ops2] == ["equal", "delete", "equal"]
