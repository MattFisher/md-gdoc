"""Frontmatter binding between a markdown file and its Google Doc."""

from typing import Any

import frontmatter


def _meta_str(post: Any, key: str) -> str | None:
    """Read a string value out of frontmatter metadata.

    Frontmatter is arbitrary YAML, so a non-string (or absent) value is treated
    as unset rather than handed back as the wrong type.
    """
    value = post.metadata.get(key)
    return value if isinstance(value, str) else None


def read(text: str) -> tuple[str | None, str | None, str]:
    post = frontmatter.loads(text)
    content = post.content
    # Normalize trailing newline: ensure content ends with \n
    if content and not content.endswith("\n"):
        content = content + "\n"
    return (
        _meta_str(post, "gdoc_id"),
        _meta_str(post, "gdoc_url"),
        content,
    )


def tab_id(text: str) -> str | None:
    return _meta_str(frontmatter.loads(text), "tab_id")


def comments_file(text: str) -> str | None:
    return _meta_str(frontmatter.loads(text), "comments_file")


def _dump(post: Any) -> str:
    out: str = frontmatter.dumps(post)
    return out if out.endswith("\n") else out + "\n"


def bind(
    text: str,
    gdoc_id: str,
    gdoc_url: str,
    tab_id: str | None = None,
    comments_file: str | None = None,
) -> str:
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
