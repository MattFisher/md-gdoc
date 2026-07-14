from md_gdoc import binding

DOC = """---
title: My doc
gdoc_id: abc123
gdoc_url: https://docs.google.com/document/d/abc123/edit
---
# Hello

Body text.
"""

NO_FM = "# Hello\n\nBody text.\n"


def test_package_imports():
    import md_gdoc

    assert md_gdoc.__version__


def test_read_bound_file():
    doc_id, url, body = binding.read(DOC)
    assert doc_id == "abc123"
    assert url.endswith("/abc123/edit")
    assert body == "# Hello\n\nBody text.\n"


def test_read_unbound_file():
    doc_id, url, body = binding.read(NO_FM)
    assert doc_id is None and url is None
    assert body == NO_FM


def test_bind_creates_frontmatter():
    out = binding.bind(NO_FM, "xyz", "https://docs.google.com/document/d/xyz/edit")
    doc_id, url, body = binding.read(out)
    assert doc_id == "xyz"
    assert body == NO_FM


def test_bind_preserves_other_keys():
    out = binding.bind(DOC, "new-id", "https://docs.google.com/document/d/new-id/edit")
    assert "title: My doc" in out
    assert binding.read(out)[0] == "new-id"


def test_read_replace_read_roundtrip():
    """Verify body trailing newline round-trip contract."""
    replaced = binding.replace_body(DOC, "New body.\n")
    _, _, body = binding.read(replaced)
    assert body == "New body.\n"


def test_replace_body_keeps_frontmatter():
    out = binding.replace_body(DOC, "New body.\n")
    doc_id, _, body = binding.read(out)
    assert doc_id == "abc123"
    assert body == "New body.\n"
