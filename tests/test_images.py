"""Extraction of data-URI images into files linked from the markdown."""

import base64

from md_gdoc import snapshot
from md_gdoc.clone import clone
from md_gdoc.images import extract_images
from md_gdoc.pull import pull
from tests.fakes import FakeApi

PNG_BYTES = b"\x89PNG-fake-image-bytes"
PNG_B64 = base64.b64encode(PNG_BYTES).decode()
JPEG_BYTES = b"\xff\xd8-fake-jpeg-bytes"
JPEG_B64 = base64.b64encode(JPEG_BYTES).decode()


def test_extracts_reference_style_data_uri(tmp_path):
    # Google's export style: reference link with an angle-bracketed definition.
    md = f"Intro.\n\n![][image1]\n\n[image1]: <data:image/png;base64,{PNG_B64}>\n"
    out = extract_images(md, tmp_path / "draft.md")
    assert "base64" not in out
    files = list((tmp_path / "draft.assets").iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".png"
    assert files[0].read_bytes() == PNG_BYTES
    assert f"draft.assets/{files[0].name}" in out


def test_extracts_inline_data_uri_preserving_alt(tmp_path):
    md = f"![diagram](data:image/png;base64,{PNG_B64})\n"
    out = extract_images(md, tmp_path / "draft.md")
    files = list((tmp_path / "draft.assets").iterdir())
    assert out == f"![diagram](draft.assets/{files[0].name})\n"


def test_same_image_extracted_once(tmp_path):
    md = f"![a](data:image/png;base64,{PNG_B64})\n\n![b](data:image/png;base64,{PNG_B64})\n"
    out = extract_images(md, tmp_path / "draft.md")
    files = list((tmp_path / "draft.assets").iterdir())
    assert len(files) == 1
    assert out.count(files[0].name) == 2


def test_extraction_is_idempotent_across_runs(tmp_path):
    md = f"![a](data:image/png;base64,{PNG_B64})\n"
    first = extract_images(md, tmp_path / "draft.md")
    second = extract_images(md, tmp_path / "draft.md")
    assert first == second
    assert len(list((tmp_path / "draft.assets").iterdir())) == 1


def test_jpeg_gets_jpg_extension(tmp_path):
    md = f"![photo](data:image/jpeg;base64,{JPEG_B64})\n"
    extract_images(md, tmp_path / "draft.md")
    files = list((tmp_path / "draft.assets").iterdir())
    assert files[0].suffix == ".jpg"
    assert files[0].read_bytes() == JPEG_BYTES


def test_no_data_uris_is_a_noop(tmp_path):
    md = "Plain text with a [link](https://example.com) and ![img](local.png).\n"
    assert extract_images(md, tmp_path / "draft.md") == md
    assert not (tmp_path / "draft.assets").exists()


def test_invalid_base64_left_untouched(tmp_path):
    md = "![x](data:image/png;base64,!!!not-base64!!!)\n"
    assert extract_images(md, tmp_path / "draft.md") == md
    assert not (tmp_path / "draft.assets").exists()


# --- integration: pull and clone extract images ---

REMOTE_WITH_IMAGE = f"Hello.\n\n![][image1]\n\n[image1]: <data:image/png;base64,{PNG_B64}>\n"


def test_pull_extracts_images_into_local_file_and_base(tmp_path):
    md = tmp_path / "draft.md"
    body = "Hello.\n"
    md.write_text(f"---\ngdoc_id: d1\ngdoc_url: u\n---\n{body}")
    snapshot.save(md, body)

    res = pull(md, FakeApi(export_md=REMOTE_WITH_IMAGE))

    assert res.state == "updated"
    text = md.read_text()
    assert "base64" not in text
    assert "draft.assets/" in text
    files = list((tmp_path / "draft.assets").iterdir())
    assert files[0].read_bytes() == PNG_BYTES
    assert "base64" not in snapshot.load(md)
    # The remote snapshot keeps the raw export so divergence checks still work.
    assert "base64," in snapshot.load_remote(md)


def test_clean_pull_migrates_data_uris_already_in_local_file(tmp_path):
    # Files pulled before extraction existed still carry data URIs; a pull
    # with no remote changes should extract them rather than leave them.
    md = tmp_path / "draft.md"
    body_with_uri = f"Hello.\n\n![][image1]\n\n[image1]: <data:image/png;base64,{PNG_B64}>\n"
    md.write_text(f"---\ngdoc_id: d1\ngdoc_url: u\n---\n{body_with_uri}")
    snapshot.save(md, body_with_uri)
    snapshot.save_remote(md, body_with_uri)

    res = pull(md, FakeApi(export_md=body_with_uri))

    assert res.state == "clean"
    text = md.read_text()
    assert "base64" not in text
    assert "draft.assets/" in text
    assert text.startswith("---\ngdoc_id: d1\n")  # frontmatter intact
    # The base snapshot moves with the file, so this isn't a phantom local edit:
    # a second pull is still clean.
    assert "base64" not in snapshot.load(md)
    assert pull(md, FakeApi(export_md=body_with_uri)).state == "clean"


def test_pull_conflict_writes_extracted_remote_copy(tmp_path):
    md = tmp_path / "draft.md"
    md.write_text("---\ngdoc_id: d1\ngdoc_url: u\n---\nHello local edit.\n")
    snapshot.save(md, "Hello.\n")

    res = pull(md, FakeApi(export_md=REMOTE_WITH_IMAGE))

    assert res.state == "conflict"
    remote_copy = res.remote_path.read_text()
    assert "base64" not in remote_copy
    assert "draft.assets/" in remote_copy


def test_clone_extracts_images(tmp_path):
    out = tmp_path / "out.md"
    clone("fake-id", str(out), FakeApi(export_md=REMOTE_WITH_IMAGE))

    text = out.read_text()
    assert "base64" not in text
    assert "out.assets/" in text
    files = list((tmp_path / "out.assets").iterdir())
    assert files[0].read_bytes() == PNG_BYTES
    assert "base64" not in snapshot.load(out)
    assert "base64," in snapshot.load_remote(out)


class _TabbedFake(FakeApi):
    def __init__(self, export_md):
        super().__init__(export_md=export_md, document={"title": "My Doc"})

    def list_tabs(self, doc_id):
        return [
            {"id": "t1", "title": "One", "index": 0},
            {"id": "t2", "title": "Two", "index": 1},
        ]


def test_clone_tabbed_extracts_images_per_tab(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    export = f"# One\n\n{REMOTE_WITH_IMAGE}\n# Two\n\nPlain text.\n"
    results = clone("fake-id", None, _TabbedFake(export))

    one = next(r for r in results if "--one" in r.path.name)
    text = one.path.read_text()
    assert "base64" not in text
    assert "my-doc--one.assets/" in text
    files = list((tmp_path / "my-doc--one.assets").iterdir())
    assert files[0].read_bytes() == PNG_BYTES
