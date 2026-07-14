import pytest

from md_gdoc.docmodel import AlignmentError, check_alignment, doc_blocks
from md_gdoc.mdblocks import parse_blocks


def _para(start, end, text):
    return {
        "startIndex": start, "endIndex": end,
        "paragraph": {"elements": [
            {"startIndex": start, "endIndex": end, "textRun": {"content": text}}
        ]},
    }


DOCUMENT = {
    "body": {"content": [
        {"endIndex": 1, "sectionBreak": {}},
        _para(1, 7, "Title\n"),
        _para(7, 8, "\n"),                       # blank separator -> skipped
        _para(8, 14, "Hello\n"),
        {"startIndex": 14, "endIndex": 30, "table": {"rows": 1, "columns": 2}},
        _para(30, 36, "Tail.\n"),
    ]}
}


def test_doc_blocks():
    blocks = doc_blocks(DOCUMENT)
    assert [(b.kind, b.start, b.end) for b in blocks] == [
        ("paragraph", 1, 7), ("paragraph", 8, 14), ("table", 14, 30), ("paragraph", 30, 36),
    ]
    assert blocks[0].text == "Title\n"


def test_alignment_ok():
    md = parse_blocks("# Title\n\nHello\n\n| a | b |\n| -- | -- |\n| 1 | 2 |\n\nTail.\n")
    check_alignment(doc_blocks(DOCUMENT), md)     # no raise


def test_alignment_count_mismatch():
    md = parse_blocks("# Title\n\nHello\n")
    with pytest.raises(AlignmentError):
        check_alignment(doc_blocks(DOCUMENT), md)


def test_alignment_kind_mismatch():
    md = parse_blocks("# Title\n\nHello\n\nNot a table\n\nTail.\n")
    with pytest.raises(AlignmentError):
        check_alignment(doc_blocks(DOCUMENT), md)
