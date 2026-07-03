from gdoc_sync.unescape import clean


def test_strips_spurious_escapes():
    assert clean(r"A \- dash and \+ plus and 3\. period") == "A - dash and + plus and 3. period\n"
    assert clean(r"Brackets \[x\] and \(y\)") == "Brackets [x] and (y)\n"
    assert clean(r"Stars \*not bold\* here") == "Stars *not bold* here\n"


def test_preserves_real_formatting():
    assert clean("**bold** and _it_ and [l](http://x)") == "**bold** and _it_ and [l](http://x)\n"


def test_double_backslash_becomes_single():
    assert clean(r"C:\\path") == r"C:\path" + "\n"


def test_normalizes_line_endings_and_blanks():
    assert clean("a\r\n\r\n\r\n\r\nb\r\n") == "a\n\nb\n"


def test_trailing_newline():
    assert clean("x") == "x\n"


def test_code_block_trailing_spaces_stripped():
    # Legacy format: code blocks from docs pushed before the code-font change
    # export as plain fence lines with hard-break trailing spaces.
    exported = "```python  \ndef f():  \n    pass  \n```  \n"
    assert clean(exported) == "```python\ndef f():\n    pass\n```\n"


def test_span_encoded_code_block_decoded():
    # Current format: code-font paragraphs export as one inline code span per
    # line; fences use multi-backtick delimiters.
    exported = (
        "Before.  \n"
        "```` ```python ````  \n"
        "`def f():`  \n"
        "    `return 1`  \n"
        "```` ``` ````  \n"
        "After.  \n"
    )
    assert clean(exported) == (
        "Before.  \n\n```python\ndef f():\n    return 1\n```\n\nAfter.  \n"
    )


def test_span_encoded_code_preserves_backticks_and_escapes():
    # Span content is emitted raw by the exporter: backticks use CommonMark
    # delimiters and backslashes must NOT be un-escaped.
    exported = (
        "```` ```md ````  \n"
        "``run `pytest` -k \"x\"``  \n"
        "`literal \\* star`  \n"
        "\n"
        "`last`  \n"
        "```` ``` ````  \n"
    )
    assert clean(exported) == (
        '```md\nrun `pytest` -k "x"\nliteral \\* star\n\nlast\n```\n'
    )


def test_span_encoded_adjacent_blocks_separated():
    exported = (
        "```` ```a ````  \n`x`  \n```` ``` ````  \n"
        "```` ```b ````  \n`y`  \n```` ``` ````  \n"
    )
    assert clean(exported) == "```a\nx\n```\n\n```b\ny\n```\n"


def test_clean_idempotent_on_local_fenced_markdown():
    local = "# T\n\n```python\ndef f():\n    pass\n```\n\nAfter.\n"
    assert clean(local) == local


def test_adjacent_code_blocks_get_blank_line():
    # Google exports back-to-back code paragraphs with a hard break, not a
    # blank line; clean() must re-separate them.
    exported = "```json  \n{}  \n```  \n```text  \nhi  \n```  \nAfter.\n"
    assert clean(exported) == "```json\n{}\n```\n\n```text\nhi\n```\n\nAfter.\n"


def test_code_block_trailing_spaces_not_outside():
    # Trailing spaces outside code blocks are preserved (GFM hard line breaks).
    md = "line one  \nline two  \n\n```text  \ncontent  \n```\n"
    result = clean(md)
    assert "line one  \n" in result
    assert "```text\n" in result
    assert "content\n" in result
