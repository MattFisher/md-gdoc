"""Drive comments -> local comments markdown file."""

from dataclasses import dataclass, field


@dataclass
class Reply:
    author: str
    created: str
    content: str


@dataclass
class CommentThread:
    id: str
    author: str
    created: str
    modified: str
    resolved: bool
    quoted: str | None
    content: str
    replies: list = field(default_factory=list)


def from_api(items):
    threads = []
    for it in items:
        if it.get("deleted"):
            continue
        threads.append(
            CommentThread(
                id=it["id"],
                author=it.get("author", {}).get("displayName", "unknown"),
                created=it.get("createdTime", ""),
                modified=it.get("modifiedTime", ""),
                resolved=bool(it.get("resolved")),
                quoted=(it.get("quotedFileContent") or {}).get("value"),
                content=it.get("content", ""),
                replies=[
                    Reply(
                        r.get("author", {}).get("displayName", "unknown"),
                        r.get("createdTime", ""),
                        r.get("content", ""),
                    )
                    for r in it.get("replies", [])
                ],
            )
        )
    return threads


def render(threads, source_name):
    lines = [f"# Comments on {source_name}", ""]
    if not threads:
        lines += ["No comments.", ""]
        return "\n".join(lines)
    for t in threads:
        state = "resolved" if t.resolved else "open"
        lines.append(f"## [{state}] {t.id} — {t.author} ({t.created})")
        lines.append("")
        if t.quoted:
            lines += [f"> {l}" for l in t.quoted.splitlines()]
            lines.append("")
        lines += [t.content, ""]
        for r in t.replies:
            lines.append(f"- **Reply — {r.author} ({r.created}):** {r.content}")
        if t.replies:
            lines.append("")
    return "\n".join(lines)
