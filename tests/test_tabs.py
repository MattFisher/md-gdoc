"""Tests for Google Docs tabs support."""

import pytest

from md_gdoc import binding, snapshot
from md_gdoc.api import _split_by_tabs
from md_gdoc.clone import _tab_filename, clone
from md_gdoc.pull import pull
from tests.fakes import FakeApi

TABS = [
    {"id": "tab-a", "title": "Overview", "index": 0},
    {"id": "tab-b", "title": "Details", "index": 1},
]

TABBED_EXPORT = """\
# Overview

Intro text.

## Section

More intro.

# Details

Detail text here.
"""


# ---------------------------------------------------------------------------
# _split_by_tabs
# ---------------------------------------------------------------------------

def test_split_two_tabs():
    result = _split_by_tabs(TABBED_EXPORT, TABS)
    assert "tab-a" in result and "tab-b" in result
    assert "Intro text." in result["tab-a"]
    assert "Detail text here." in result["tab-b"]
    # Tab header lines are not included in the body
    assert "# Overview" not in result["tab-a"]
    assert "# Details" not in result["tab-b"]


def test_split_preserves_sub_headings():
    result = _split_by_tabs(TABBED_EXPORT, TABS)
    assert "## Section" in result["tab-a"]


def test_split_three_tabs():
    tabs = [
        {"id": "t1", "title": "A", "index": 0},
        {"id": "t2", "title": "B", "index": 1},
        {"id": "t3", "title": "C", "index": 2},
    ]
    md = "# A\n\nalpha\n\n# B\n\nbeta\n\n# C\n\ngamma\n"
    result = _split_by_tabs(md, tabs)
    assert result["t1"].strip() == "alpha"
    assert result["t2"].strip() == "beta"
    assert result["t3"].strip() == "gamma"


def test_split_content_before_first_marker_goes_to_first_tab():
    tabs = [
        {"id": "t1", "title": "Tab1", "index": 0},
        {"id": "t2", "title": "Tab2", "index": 1},
    ]
    md = "Preamble content.\n\n# Tab2\n\nSecond tab body.\n"
    result = _split_by_tabs(md, tabs)
    assert "Preamble content." in result["t1"]
    assert "Second tab body." in result["t2"]


def test_split_no_markers_returns_all_to_first_tab():
    tabs = [
        {"id": "t1", "title": "Tab1", "index": 0},
        {"id": "t2", "title": "Tab2", "index": 1},
    ]
    md = "No tab headers here.\n"
    result = _split_by_tabs(md, tabs)
    assert result == {"t1": md}


def test_split_ignores_h1s_that_are_not_tab_titles():
    tabs = [
        {"id": "t1", "title": "Overview", "index": 0},
        {"id": "t2", "title": "Details", "index": 1},
    ]
    md = "# Overview\n\n# Not A Tab\n\ncontent\n\n# Details\n\ndetail\n"
    result = _split_by_tabs(md, tabs)
    # "# Not A Tab" is not a tab title, so it stays in tab-a's body
    assert "# Not A Tab" in result["t1"]
    assert "detail" in result["t2"]


# ---------------------------------------------------------------------------
# binding.tab_id / binding.bind with tab_id
# ---------------------------------------------------------------------------

def test_binding_tab_id_returns_none_when_absent():
    assert binding.tab_id("# Hello\n\nBody.\n") is None


def test_binding_tab_id_reads_from_frontmatter():
    text = "---\ngdoc_id: abc\ntab_id: xyz\n---\nBody.\n"
    assert binding.tab_id(text) == "xyz"


def test_binding_bind_with_tab_id():
    text = "# Hello\n\nBody.\n"
    out = binding.bind(text, "doc-1", "https://docs.google.com/document/d/doc-1/edit", tab_id="tab-99")
    assert binding.tab_id(out) == "tab-99"
    # Existing binding fields still correct
    doc_id, url, body = binding.read(out)
    assert doc_id == "doc-1"
    assert "Body." in body


def test_binding_bind_without_tab_id_omits_field():
    out = binding.bind("Body.\n", "d", "u")
    assert "tab_id" not in out


# ---------------------------------------------------------------------------
# _tab_filename
# ---------------------------------------------------------------------------

def test_tab_filename():
    assert _tab_filename("My Doc", "Overview") == "my-doc--overview.md"
    assert _tab_filename("Project", "Tab Two") == "project--tab-two.md"


# ---------------------------------------------------------------------------
# clone with tabs
# ---------------------------------------------------------------------------

class _TabbedApi(FakeApi):
    """FakeApi that advertises two tabs and returns split export."""

    def __init__(self, title="Doc"):
        super().__init__(export_md=TABBED_EXPORT)
        self.document = {"title": title, "body": {"content": []}}

    def list_tabs(self, doc_id):
        return list(TABS)


def test_clone_tabbed_creates_two_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = clone("fake-id", None, _TabbedApi())
    assert isinstance(results, list)
    assert len(results) == 2


def test_clone_tabbed_filenames_derive_from_titles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = clone("fake-id", None, _TabbedApi(title="My Doc"))
    names = {r.path.name for r in results}
    assert "my-doc--overview.md" in names
    assert "my-doc--details.md" in names


def test_clone_tabbed_writes_tab_id_to_frontmatter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = clone("fake-id", None, _TabbedApi())
    ids = {binding.tab_id(r.path.read_text()) for r in results}
    assert ids == {"tab-a", "tab-b"}


def test_clone_tabbed_splits_content_correctly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = clone("fake-id", None, _TabbedApi())
    overview = next(r for r in results if "overview" in r.path.name)
    details = next(r for r in results if "details" in r.path.name)
    _, _, overview_body = binding.read(overview.path.read_text())
    _, _, details_body = binding.read(details.path.read_text())
    assert "Intro text." in overview_body
    assert "Detail text here." in details_body


def test_clone_tabbed_saves_snapshots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = clone("fake-id", None, _TabbedApi())
    for r in results:
        assert snapshot.load(r.path) is not None
        assert snapshot.load_remote(r.path) is not None


def test_clone_tabbed_writes_shared_comments_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clone("fake-id", None, _TabbedApi(title="My Doc"))
    # One shared comments file, not one per tab
    comments_files = list(tmp_path.glob("*.comments.md"))
    assert len(comments_files) == 1
    assert comments_files[0].name == "my-doc.md.comments.md"


def test_clone_tabbed_frontmatter_has_comments_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = clone("fake-id", None, _TabbedApi(title="My Doc"))
    for r in results:
        assert binding.comments_file(r.path.read_text()) == "my-doc.md.comments.md"


def test_clone_tabbed_rejects_explicit_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="multiple tabs"):
        clone("fake-id", str(tmp_path / "out.md"), _TabbedApi())


def test_clone_tabbed_accepts_directory_arg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "my-doc"
    sub.mkdir()
    results = clone("fake-id", str(sub), _TabbedApi(title="My Doc"))
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(r.path.parent == sub for r in results)


def test_clone_tabbed_creates_directory_if_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "new-folder"
    results = clone("fake-id", str(sub) + "/", _TabbedApi())
    assert sub.is_dir()
    assert all(r.path.parent == sub for r in results)


# ---------------------------------------------------------------------------
# pull with tab_id
# ---------------------------------------------------------------------------

class _TabPullApi(FakeApi):
    """FakeApi that returns different content for tab vs full export."""

    def __init__(self, tab_body):
        super().__init__(export_md=TABBED_EXPORT)
        self._tab_body = tab_body

    def list_tabs(self, doc_id):
        return list(TABS)

    def export_tab_markdown(self, doc_id, tab_id):
        return self._tab_body


def test_pull_uses_tab_export_when_tab_id_set(tmp_path):
    tab_body = "Updated tab content.\n"
    # Create a file that was cloned from a tab
    md = tmp_path / "doc--overview.md"
    md.write_text(
        "---\ngdoc_id: fake-id\ngdoc_url: u\ntab_id: tab-a\n---\nOld content.\n"
    )
    snapshot.save(md, "Old content.\n")
    snapshot.save_remote(md, "Old content.\n")

    api = _TabPullApi(tab_body)
    res = pull(md, api)
    assert res.state == "updated"
    _, _, body = binding.read(md.read_text())
    assert "Updated tab content." in body
