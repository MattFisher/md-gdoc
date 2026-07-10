"""Frontmatter binding between a markdown file and its Google Doc."""

import frontmatter


def read(text: str) -> tuple[str | None, str | None, str]:
    post = frontmatter.loads(text)
    content = post.content
    # Normalize trailing newline: ensure content ends with \n
    if content and not content.endswith("\n"):
        content = content + "\n"
    return (
        post.metadata.get("gdoc_id"),
        post.metadata.get("gdoc_url"),
        content,
    )


def tab_id(text: str) -> str | None:
    return frontmatter.loads(text).metadata.get("tab_id")


def comments_file(text: str) -> str | None:
    return frontmatter.loads(text).metadata.get("comments_file")


def _dump(post):
    out = frontmatter.dumps(post)
    return out if out.endswith("\n") else out + "\n"


def bind(text: str, gdoc_id: str, gdoc_url: str, tab_id=None, comments_file=None) -> str:
    post = frontmatter.loads(text)
    post.metadata["gdoc_id"] = gdoc_id
    post.metadata["gdoc_url"] = gdoc_url
    if tab_id is not None:
        post.metadata["tab_id"] = tab_id
    if comments_file is not None:
        post.metadata["comments_file"] = comments_file
    return _dump(post)


def replace_body(text: str, new_body: str) -> str:
    post = frontmatter.loads(text)
    post.content = new_body.rstrip("\n")
    return _dump(post)
