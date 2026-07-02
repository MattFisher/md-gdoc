"""Frontmatter binding between a markdown file and its Google Doc."""

import frontmatter


def read(text):
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


def bind(text, gdoc_id, gdoc_url):
    post = frontmatter.loads(text)
    post.metadata["gdoc_id"] = gdoc_id
    post.metadata["gdoc_url"] = gdoc_url
    return _dump(post)


def replace_body(text, new_body):
    post = frontmatter.loads(text)
    post.content = new_body.rstrip("\n")
    return _dump(post)
