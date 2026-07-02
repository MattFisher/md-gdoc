from gdoc_sync.requests_builder import Run, inline_runs, block_requests, content_text
from gdoc_sync.mdblocks import Block


def test_plain_text():
    assert inline_runs("hello world") == [Run("hello world")]


def test_bold_italic_link():
    runs = inline_runs("a **b** _c_ [d](http://e)")
    assert runs == [
        Run("a "),
        Run("b", bold=True),
        Run(" "),
        Run("c", italic=True),
        Run(" "),
        Run("d", link="http://e"),
    ]


def test_nested_bold_italic():
    assert inline_runs("**bold _both_**") == [
        Run("bold ", bold=True),
        Run("both", bold=True, italic=True),
    ]


def test_code_inline_kept_literal():
    assert inline_runs("run `pytest` now") == [Run("run `pytest` now")]


def test_softbreak_is_space():
    assert inline_runs("line one\nline two") == [Run("line one line two")]


def test_content_text_strips_markers():
    assert content_text(Block("heading", "## Hi", level=2)) == "Hi"
    assert content_text(Block("list_item", "- item text")) == "item text"
    assert content_text(Block("quote", "> line one\n> line two")) == "line one\nline two"
    assert content_text(Block("paragraph", "plain")) == "plain"


def test_paragraph_requests():
    reqs = block_requests(Block("paragraph", "Hello **world**"), 10)
    assert reqs[0] == {"insertText": {"location": {"index": 10}, "text": "Hello world\n"}}
    style = reqs[1]["updateTextStyle"]
    assert style["range"] == {"startIndex": 16, "endIndex": 21}
    assert style["textStyle"] == {"bold": True} and style["fields"] == "bold"
    para = reqs[-1]["updateParagraphStyle"]
    assert para["paragraphStyle"]["namedStyleType"] == "NORMAL_TEXT"
    assert para["range"] == {"startIndex": 10, "endIndex": 22}


def test_heading_requests():
    reqs = block_requests(Block("heading", "## Hi", level=2), 1)
    para = reqs[-1]["updateParagraphStyle"]
    assert para["paragraphStyle"]["namedStyleType"] == "HEADING_2"


def test_link_run_style():
    reqs = block_requests(Block("paragraph", "[x](http://y)"), 1)
    style = reqs[1]["updateTextStyle"]
    assert style["textStyle"]["link"] == {"url": "http://y"}
    assert style["fields"] == "link"


def test_list_item_requests_nested():
    reqs = block_requests(Block("list_item", "  - deep", level=1), 5)
    assert reqs[0]["insertText"]["text"] == "\tdeep\n"
    bullets = reqs[-1]["createParagraphBullets"]
    assert bullets["bulletPreset"] == "BULLET_DISC_CIRCLE_SQUARE"
    assert bullets["range"] == {"startIndex": 5, "endIndex": 11}


def test_ordered_list_preset():
    reqs = block_requests(Block("list_item", "1. one", ordered=True), 1)
    assert reqs[-1]["createParagraphBullets"]["bulletPreset"] == "NUMBERED_DECIMAL_ALPHA_ROMAN"


def test_quote_indent():
    reqs = block_requests(Block("quote", "> q"), 1)
    para = reqs[-1]["updateParagraphStyle"]
    assert para["paragraphStyle"]["indentStart"] == {"magnitude": 36, "unit": "PT"}
    assert "indentStart" in para["fields"]
