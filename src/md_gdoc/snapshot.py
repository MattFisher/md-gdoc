"""Local .sync/ snapshots: the merge base from the last successful push/pull.

Two files are maintained:
  .base        — local body at last push/pull (diff base for local edits)
  .base.remote — Google's cleaned export at last push/pull (divergence check)
"""

from pathlib import Path


def path_for(md_path):
    md_path = Path(md_path)
    return md_path.parent / ".sync" / (md_path.name + ".base")


def remote_path_for(md_path):
    md_path = Path(md_path)
    return md_path.parent / ".sync" / (md_path.name + ".base.remote")


def load(md_path):
    p = path_for(md_path)
    return p.read_text(encoding="utf-8") if p.exists() else None


def load_remote(md_path):
    p = remote_path_for(md_path)
    return p.read_text(encoding="utf-8") if p.exists() else None


def save(md_path, body):
    p = path_for(md_path)
    p.parent.mkdir(exist_ok=True)
    p.write_text(body, encoding="utf-8")


def save_remote(md_path, body):
    p = remote_path_for(md_path)
    p.parent.mkdir(exist_ok=True)
    p.write_text(body, encoding="utf-8")
