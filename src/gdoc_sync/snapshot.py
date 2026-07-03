"""Local .sync/ snapshots: the merge base from the last successful push/pull."""

from pathlib import Path


def path_for(md_path):
    md_path = Path(md_path)
    return md_path.parent / ".sync" / (md_path.name + ".base")


def load(md_path):
    p = path_for(md_path)
    return p.read_text() if p.exists() else None


def save(md_path, body):
    p = path_for(md_path)
    p.parent.mkdir(exist_ok=True)
    p.write_text(body)
