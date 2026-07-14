from md_gdoc.comments import CommentThread, Reply, from_api, render

API_ITEMS = [
    {
        "id": "c1",
        "author": {"displayName": "Sarah"},
        "createdTime": "2026-07-01T09:00:00Z",
        "modifiedTime": "2026-07-01T10:00:00Z",
        "resolved": False,
        "quotedFileContent": {"value": "the anchored text"},
        "content": "This claim needs a source.",
        "replies": [
            {"author": {"displayName": "Matt"}, "createdTime": "2026-07-01T11:00:00Z",
             "content": "Good point, will add."}
        ],
    },
    {"id": "c2", "author": {"displayName": "Bob"}, "createdTime": "2026-07-01T09:30:00Z",
     "modifiedTime": "2026-07-01T09:30:00Z", "resolved": True, "content": "Old note",
     "replies": []},
    {"id": "c3", "deleted": True, "content": "", "replies": []},
]


def test_from_api():
    threads = from_api(API_ITEMS)
    assert [t.id for t in threads] == ["c1", "c2"]           # deleted skipped
    t = threads[0]
    assert t.author == "Sarah" and t.quoted == "the anchored text"
    assert not t.resolved and threads[1].resolved
    assert t.replies == [Reply("Matt", "2026-07-01T11:00:00Z", "Good point, will add.")]
    assert threads[1].quoted is None


def test_render():
    out = render(from_api(API_ITEMS), "draft.md")
    assert out.startswith("# Comments on draft.md")
    assert "## [open] c1 — Sarah" in out
    assert "> the anchored text" in out
    assert "This claim needs a source." in out
    assert "- **Reply — Matt" in out
    assert "## [resolved] c2 — Bob" in out


def test_render_empty():
    assert "No comments." in render([], "draft.md")
