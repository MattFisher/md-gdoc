from gdoc_sync.mdblocks import Block, parse_blocks, unsupported

MD = """# Title

Intro paragraph with **bold**.

- first item
- second item
  nested continuation
  - nested item
1. numbered one

> A quote line
> continued.

| h1 | h2 |
| -- | -- |
| a  | b  |

Final paragraph.
"""


def test_kinds_in_order():
    kinds = [b.kind for b in parse_blocks(MD)]
    assert kinds == [
        "heading", "paragraph",
        "list_item", "list_item", "list_item", "list_item",
        "quote", "table", "paragraph",
    ]


def test_heading_level():
    assert parse_blocks("## Two\n")[0].level == 2


def test_list_item_details():
    blocks = [b for b in parse_blocks(MD) if b.kind == "list_item"]
    assert blocks[0].source == "- first item"
    assert blocks[1].source == "- second item\n  nested continuation"
    assert blocks[2].level == 1                    # "  - nested item"
    assert blocks[3].ordered is True               # "1. numbered one"


def test_table_is_one_block():
    table = [b for b in parse_blocks(MD) if b.kind == "table"][0]
    assert table.source.count("\n") == 2


def test_source_roundtrip_blocks_join():
    blocks = parse_blocks(MD)
    rejoined = "\n\n".join(b.source for b in blocks)
    # Same block sources, ignoring exact blank-line counts
    assert [b.source for b in parse_blocks(rejoined)] == [b.source for b in blocks]


def test_unsupported_detection():
    md = "Text\n\n![alt](img.png)\n\n```py\ncode\n```\n\n[^1]: a footnote\n"
    blocks = parse_blocks(md)
    assert [b.kind for b in blocks] == ["paragraph", "other", "other", "other"]
    descriptions = unsupported(blocks)
    assert len(descriptions) == 3
    assert any("image" in d for d in descriptions)


def test_empty_input():
    assert parse_blocks("") == []
