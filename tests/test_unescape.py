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
    # Simulates Google export of a code block stored with \r soft-breaks:
    # each line gains trailing spaces on export.
    exported = "```python  \ndef f():  \n    pass  \n```  \n"
    assert clean(exported) == "```python\ndef f():\n    pass\n```\n"


def test_code_block_trailing_spaces_not_outside():
    # Trailing spaces outside code blocks are preserved (GFM hard line breaks).
    md = "line one  \nline two  \n\n```text  \ncontent  \n```\n"
    result = clean(md)
    assert "line one  \n" in result
    assert "```text\n" in result
    assert "content\n" in result
