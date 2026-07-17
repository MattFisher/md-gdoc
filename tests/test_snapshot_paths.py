from md_gdoc import snapshot
from md_gdoc.api import GDocsApi


def test_snapshot_roundtrip(tmp_path):
    md = tmp_path / "draft.md"
    md.write_text("hello\n")
    assert snapshot.load(md) is None
    snapshot.save(md, "hello\n")
    assert snapshot.path_for(md) == tmp_path / ".sync" / "draft.md.base"
    assert snapshot.load(md) == "hello\n"


def test_doc_url():
    assert GDocsApi.doc_url("abc") == "https://docs.google.com/document/d/abc/edit"
