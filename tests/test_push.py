import pytest

from gdoc_sync import binding, snapshot
from gdoc_sync.push import push
from tests.fakes import FakeApi

BODY = "# T\n\nOne.\n\nTwo.\n"
BOUND = f"---\ngdoc_id: d1\ngdoc_url: u\n---\n{BODY}"


def _doc(paragraphs):
    content, idx = [{"endIndex": 1, "sectionBreak": {}}], 1
    for p in paragraphs:
        end = idx + len(p) + 1
        content.append({
            "startIndex": idx, "endIndex": end,
            "paragraph": {"elements": [
                {"startIndex": idx, "endIndex": end, "textRun": {"content": p + "\n"}}
            ]},
        })
        idx = end
    return {"body": {"content": content}}


DOC = _doc(["T", "One.", "Two."])


def _setup(tmp_path, local, snap=BODY):
    md = tmp_path / "draft.md"
    md.write_text(local)
    if snap is not None:
        snapshot.save(md, snap)
    return md


def test_first_push_binds_and_snapshots(tmp_path):
    md = tmp_path / "draft.md"
    md.write_text(BODY)
    res = push(md, FakeApi(export_md=BODY))
    assert res.state == "created"
    assert binding.read(md.read_text())[0] == "fake-id"
    assert snapshot.load(md) == BODY          # local snapshot = what we sent
    assert snapshot.load_remote(md) == BODY   # remote snapshot = what Google returned


def test_noop_when_unchanged(tmp_path):
    md = _setup(tmp_path, BOUND)
    res = push(md, FakeApi(export_md=BODY, document=DOC))
    assert res.state == "noop"


def test_revision_push_targets_changed_block(tmp_path):
    local = BOUND.replace("Two.", "Two edited.")
    local_body = binding.read(local)[2]
    post_edit_remote = BODY.replace("Two.", "Two edited.")
    md = _setup(tmp_path, local)
    api = FakeApi(export_md=BODY, document=DOC, export_md_after_update=post_edit_remote)
    res = push(md, api, yes=True)
    assert res.state == "pushed"
    assert len(api.batch_updates) == 1               # one atomic call
    reqs = api.batch_updates[0]
    # _doc layout: "T\n" -> 1..3, "One.\n" -> 3..8, "Two.\n" -> 8..13
    delete = [r for r in reqs if "deleteContentRange" in r][0]["deleteContentRange"]
    assert delete["range"] == {"startIndex": 8, "endIndex": 13}
    inserts = [r for r in reqs if "insertText" in r]
    assert inserts[0]["insertText"]["text"] == "Two edited.\n"
    assert snapshot.load(md) == local_body             # local snapshot = what we sent
    assert snapshot.load_remote(md) == post_edit_remote  # remote snapshot = Google's export


def test_divergence_aborts(tmp_path):
    md = _setup(tmp_path, BOUND.replace("Two.", "Two edited."))
    api = FakeApi(export_md="# T\n\nOne.\n\nRemote change.\n", document=DOC)
    with pytest.raises(SystemExit, match="pull"):
        push(md, api, yes=True)


def test_orphan_warning_aborts_without_confirmation(tmp_path):
    md = _setup(tmp_path, BOUND.replace("Two.", "Two edited."))
    api = FakeApi(export_md=BODY, document=DOC, comments=[{
        "id": "c1", "author": {"displayName": "S"}, "createdTime": "t",
        "modifiedTime": "t", "resolved": False, "content": "?",
        "quotedFileContent": {"value": "Two."}, "replies": [],
    }])
    with pytest.raises(SystemExit):
        push(md, api, confirm=lambda prompt: "n")
    res = push(md, api, confirm=lambda prompt: "y")
    assert res.state == "pushed" and res.orphaned == ["Two."]


def test_unsupported_changed_block_aborts(tmp_path):
    local = BOUND.replace("Two.", "![img](x.png)")
    md = _setup(tmp_path, local)
    with pytest.raises(SystemExit, match="replace"):
        push(md, FakeApi(export_md=BODY, document=DOC), yes=True)


def test_replace_path(tmp_path):
    md = _setup(tmp_path, BOUND.replace("Two.", "Anything **new**."))
    api = FakeApi(export_md=BODY, document=DOC)
    res = push(md, api, replace=True, yes=True)
    assert res.state == "replaced"
    assert api.replaced and "Anything" in api.replaced[0]


def test_missing_snapshot_requires_replace(tmp_path):
    md = _setup(tmp_path, BOUND.replace("Two.", "Two edited."), snap=None)
    with pytest.raises(SystemExit):
        push(md, FakeApi(export_md=BODY, document=DOC), yes=True)


def test_table_with_sibling_insert_aborts(tmp_path):
    """Inserting a table alongside another block in one op must abort with --replace hint."""
    # Base: single paragraph (no heading, just one block)
    base_body = "Intro.\n"
    base_bound = f"---\ngdoc_id: d1\ngdoc_url: u\n---\n{base_body}"
    base_doc = _doc(["Intro."])
    # New: the original paragraph is untouched, but we insert a table AND a new paragraph
    # after it — but because the base only had one block and new has three, the diff will
    # produce an insert op covering both the table and the trailing paragraph at once.
    new_body = "Intro.\n\n| h1 | h2 |\n| -- | -- |\n| a  | b  |\n\nExtra.\n"
    new_bound = f"---\ngdoc_id: d1\ngdoc_url: u\n---\n{new_body}"
    md = _setup(tmp_path, new_bound, snap=base_body)
    api = FakeApi(export_md=base_body, document=base_doc)
    with pytest.raises(SystemExit, match="--replace"):
        push(md, api, yes=True)
