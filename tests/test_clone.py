import pytest

from md_gdoc import binding, snapshot
from md_gdoc.clone import _extract_doc_id, _title_to_filename, clone
from tests.fakes import FakeApi

BODY = "# Hello\n\nWorld.\n"


def _api(body=BODY, title="My Doc", comments=None):
    api = FakeApi(export_md=body, comments=comments or [])
    api.document = {"title": title, "body": {"content": []}}
    return api


# --- unit helpers ---

def test_extract_doc_id_from_url():
    url = "https://docs.google.com/document/d/abc123XYZ/edit"
    assert _extract_doc_id(url) == "abc123XYZ"


def test_extract_doc_id_bare():
    assert _extract_doc_id("abc123XYZ") == "abc123XYZ"


def test_extract_doc_id_invalid():
    with pytest.raises(SystemExit):
        _extract_doc_id("not a url or id!")


def test_title_to_filename():
    assert _title_to_filename("My Great Doc") == "my-great-doc.md"
    assert _title_to_filename("Hello, World!") == "hello-world.md"
    assert _title_to_filename("") == "document.md"


# --- clone behaviour ---

def test_clone_creates_file(tmp_path):
    res = clone("fake-id", str(tmp_path / "out.md"), _api())
    assert res.path == tmp_path / "out.md"
    assert (tmp_path / "out.md").exists()


def test_clone_writes_frontmatter_and_body(tmp_path):
    clone("fake-id", str(tmp_path / "out.md"), _api())
    doc_id, url, body = binding.read((tmp_path / "out.md").read_text())
    assert doc_id == "fake-id"
    assert "fake-id" in url
    assert "Hello" in body


def test_clone_saves_snapshots(tmp_path):
    clone("fake-id", str(tmp_path / "out.md"), _api())
    md = tmp_path / "out.md"
    assert snapshot.load(md) is not None
    assert snapshot.load_remote(md) is not None


def test_clone_writes_comments_file(tmp_path):
    clone("fake-id", str(tmp_path / "out.md"), _api())
    assert (tmp_path / "out.md.comments.md").exists()


def test_clone_derives_filename_from_title(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = clone("fake-id", None, _api(title="Project Notes"))
    assert res.path.name == "project-notes.md"
    assert res.path.exists()


def test_clone_refuses_to_overwrite(tmp_path):
    out = tmp_path / "out.md"
    out.write_text("existing")
    with pytest.raises(SystemExit, match="already exists"):
        clone("fake-id", str(out), _api())


def test_clone_accepts_full_url(tmp_path):
    url = "https://docs.google.com/document/d/fake-id/edit"
    clone(url, str(tmp_path / "out.md"), _api())
    _, _, body = binding.read((tmp_path / "out.md").read_text())
    assert "Hello" in body


def test_clone_pull_is_clean_after(tmp_path):
    """After clone, pull should report clean with no snapshot update needed."""
    from md_gdoc.pull import pull

    clone("fake-id", str(tmp_path / "out.md"), _api())
    res = pull(tmp_path / "out.md", _api())
    assert res.state == "clean"
