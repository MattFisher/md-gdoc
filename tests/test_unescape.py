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
