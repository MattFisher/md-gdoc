"""End-to-end tests against the real Drive/Docs APIs.

Opt-in only: requires RUN_MD_GDOC_E2E=1 and OAuth credentials
(MD_GDOC_CREDENTIALS / MD_GDOC_TOKEN or the default config paths).
A plain `pytest` run skips everything here. Docs are created inside the
Drive folder named by MD_GDOC_E2E_FOLDER (default "md-gdoc-e2e") and
deleted in teardown.

Regenerate the golden export after an intentional change:

    RUN_MD_GDOC_E2E=1 python -m tests.e2e.test_end_to_end --generate
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "full_features.md"
EXPECTED = FIXTURES / "full_features.expected.md"
FOLDER = os.environ.get("MD_GDOC_E2E_FOLDER", "md-gdoc-e2e")

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MD_GDOC_E2E") != "1",
    reason="e2e disabled (set RUN_MD_GDOC_E2E=1)",
)


@pytest.fixture(scope="module")
def api():
    from md_gdoc.api import GDocsApi
    from md_gdoc.auth import get_credentials

    return GDocsApi(get_credentials())


@pytest.fixture
def workdir(tmp_path):
    md = tmp_path / "full_features.md"
    shutil.copy(SOURCE, md)
    return md


@pytest.fixture
def pushed(api, workdir):
    """Push the fixture, yield (md_path, doc_id), delete the doc after."""
    from md_gdoc import binding, snapshot
    from md_gdoc.mdblocks import parse_blocks
    from md_gdoc.push import _insert_blocks
    from md_gdoc.unescape import clean

    folder_id = api.find_or_create_folder(FOLDER)
    body = SOURCE.read_text()
    doc_id, url = api.create_doc("md-gdoc e2e", folder_id)
    _insert_blocks(doc_id, parse_blocks(body), api)
    workdir.write_text(binding.bind(workdir.read_text(), doc_id, url))
    snapshot.save(workdir, body)
    snapshot.save_remote(workdir, clean(api.export_markdown(doc_id)))
    try:
        yield workdir, doc_id
    finally:
        api.delete_file(doc_id)


def test_round_trip_matches_golden(api, pushed):
    from md_gdoc.unescape import clean

    _, doc_id = pushed
    exported = clean(api.export_markdown(doc_id))
    assert EXPECTED.exists(), "golden missing — run --generate first"
    assert exported == EXPECTED.read_text()


def test_comment_retrieval(api, pushed):
    from md_gdoc.pull import pull

    md, doc_id = pushed
    api.create_comment(doc_id, "e2e comment body", quoted="Intro paragraph")
    res = pull(md, api)
    assert res.comment_count >= 1
    text = (md.parent / (md.name + ".comments.md")).read_text()
    assert "e2e comment body" in text
    assert "Intro paragraph" in text


def test_anchor_preservation_and_orphaning(api, pushed):
    from md_gdoc.push import push

    md, doc_id = pushed
    api.create_comment(doc_id, "anchored to closing", quoted="Closing paragraph.")

    # Edit a DIFFERENT paragraph -> anchor must survive.
    md.write_text(md.read_text().replace("Intro paragraph", "Intro paragraph edited"))
    res = push(md, api, yes=True)
    assert res.state == "pushed"
    assert res.orphaned == []
    comment = next(c for c in api.list_comments(doc_id) if c["content"] == "anchored to closing")
    assert comment.get("quotedFileContent", {}).get("value")  # still anchored

    # Now edit the anchored paragraph -> push reports the orphan.
    md.write_text(md.read_text().replace("Closing paragraph.", "Closing paragraph rewritten."))
    res = push(md, api, yes=True)
    assert res.orphaned == ["Closing paragraph."]


def test_divergence_guard(api, pushed):
    from md_gdoc.push import push

    md, doc_id = pushed
    api.batch_update(doc_id, [{"insertText": {"location": {"index": 1}, "text": "Remote edit!\n"}}])
    md.write_text(md.read_text().replace("Intro paragraph", "Local edit"))
    with pytest.raises(SystemExit, match="pull"):
        push(md, api, yes=True)


def _generate():
    from md_gdoc.api import GDocsApi
    from md_gdoc.auth import get_credentials
    from md_gdoc.mdblocks import parse_blocks
    from md_gdoc.push import _insert_blocks
    from md_gdoc.unescape import clean

    api = GDocsApi(get_credentials())
    folder_id = api.find_or_create_folder(FOLDER)
    doc_id, _ = api.create_doc("md-gdoc golden", folder_id)
    _insert_blocks(doc_id, parse_blocks(SOURCE.read_text()), api)
    try:
        EXPECTED.write_text(clean(api.export_markdown(doc_id)))
        print(f"wrote {EXPECTED}")
    finally:
        api.delete_file(doc_id)


if __name__ == "__main__" and "--generate" in sys.argv:
    _generate()
