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


def _dump(post):
    out = frontmatter.dumps(post)
    return out if out.endswith("\n") else out + "\n"


def bind(text: str, gdoc_id: str, gdoc_url: str) -> str:
    post = frontmatter.loads(text)
    post.metadata["gdoc_id"] = gdoc_id
    post.metadata["gdoc_url"] = gdoc_url
    return _dump(post)


def replace_body(text: str, new_body: str) -> str:
    post = frontmatter.loads(text)
    post.content = new_body.rstrip("\n")
    return _dump(post)
