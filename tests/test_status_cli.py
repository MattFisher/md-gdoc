from md_gdoc import snapshot
from md_gdoc.status import status
from tests.fakes import FakeApi

BODY = "# T\n\nHello.\n"
BOUND = f"---\ngdoc_id: d1\ngdoc_url: u\n---\n{BODY}"


def test_status_clean(tmp_path):
    md = tmp_path / "draft.md"
    md.write_text(BOUND)
    snapshot.save(md, BODY)
    res = status(md, FakeApi(export_md=BODY))
    assert res.remote_changed is False and res.open_comments == 0


def test_status_remote_changed_and_comments(tmp_path):
    md = tmp_path / "draft.md"
    md.write_text(BOUND)
    snapshot.save(md, BODY)
    api = FakeApi(export_md="# T\n\nEdited.\n", comments=[
        {"id": "c1", "author": {"displayName": "S"}, "createdTime": "t",
         "modifiedTime": "t", "resolved": False, "content": "x", "replies": []},
        {"id": "c2", "author": {"displayName": "S"}, "createdTime": "t",
         "modifiedTime": "t", "resolved": True, "content": "y", "replies": []},
    ])
    res = status(md, api)
    assert res.remote_changed is True and res.open_comments == 1


def test_cli_help_needs_no_credentials(capsys):
    import pytest

    from md_gdoc.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "push" in capsys.readouterr().out
