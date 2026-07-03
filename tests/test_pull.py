import pytest

from gdoc_sync import binding, snapshot
from gdoc_sync.pull import pull
from tests.fakes import FakeApi

BODY = "# T\n\nHello.\n"
BOUND = f"---\ngdoc_id: d1\ngdoc_url: https://docs.google.com/document/d/d1/edit\n---\n{BODY}"


def _setup(tmp_path, local=BOUND, snap=BODY):
    md = tmp_path / "draft.md"
    md.write_text(local)
    if snap is not None:
        snapshot.save(md, snap)
    return md


def test_pull_clean(tmp_path):
    md = _setup(tmp_path)
    res = pull(md, FakeApi(export_md=BODY))
    assert res.state == "clean" and res.comment_count == 0
    assert (tmp_path / "draft.md.comments.md").exists()


def test_pull_remote_updated(tmp_path):
    md = _setup(tmp_path)
    res = pull(md, FakeApi(export_md="# T\n\nHello edited.\n"))
    assert res.state == "updated"
    assert "Hello edited." in binding.read(md.read_text())[2]
    assert snapshot.load(md) == "# T\n\nHello edited.\n"


def test_pull_conflict(tmp_path):
    local = BOUND.replace("Hello.", "Hello local.")
    md = _setup(tmp_path, local=local)
    res = pull(md, FakeApi(export_md="# T\n\nHello remote.\n"))
    assert res.state == "conflict"
    assert res.remote_path.read_text() == "# T\n\nHello remote.\n"
    assert "Hello local." in md.read_text()          # untouched
    assert snapshot.load(md) == BODY                 # untouched


def test_pull_missing_snapshot_differing(tmp_path):
    md = _setup(tmp_path, snap=None)
    res = pull(md, FakeApi(export_md="# T\n\nDifferent.\n"))
    assert res.state == "conflict"


def test_pull_unbound_file_exits(tmp_path):
    md = tmp_path / "draft.md"
    md.write_text(BODY)
    with pytest.raises(SystemExit):
        pull(md, FakeApi())


def test_pull_writes_comments(tmp_path):
    md = _setup(tmp_path)
    api = FakeApi(export_md=BODY, comments=[{
        "id": "c1", "author": {"displayName": "Sarah"}, "createdTime": "t",
        "modifiedTime": "t", "resolved": False, "content": "hi", "replies": [],
    }])
    res = pull(md, api)
    assert res.comment_count == 1
    assert "Sarah" in (tmp_path / "draft.md.comments.md").read_text()
