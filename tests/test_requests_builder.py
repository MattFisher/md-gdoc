from gdoc_sync.requests_builder import Run, inline_runs


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
