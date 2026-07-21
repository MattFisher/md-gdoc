"""md-gdoc command line interface."""

from __future__ import annotations

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int | None:
    parser = argparse.ArgumentParser(
        prog="md-gdoc",
        description="Sync local markdown with Google Docs (push/pull/status).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push", help="create or update the Google Doc from the file")
    p_push.add_argument("file")
    p_push.add_argument(
        "--replace",
        action="store_true",
        help="re-import the whole doc (orphans ALL comment anchors)",
    )
    p_push.add_argument(
        "--force", action="store_true", help="push even if the remote doc has unpulled changes"
    )
    p_push.add_argument("--yes", action="store_true", help="skip confirmation prompts")

    p_pull = sub.add_parser("pull", help="fetch comments and remote edits")
    p_pull.add_argument("file")

    p_clone = sub.add_parser("clone", help="create a local file from an existing Google Doc")
    p_clone.add_argument("url", metavar="URL_OR_ID", help="Google Doc URL or bare document ID")
    p_clone.add_argument(
        "file", nargs="?", metavar="FILE", help="output path (default: derived from document title)"
    )

    p_status = sub.add_parser("status", help="check for remote changes and open comments")
    p_status.add_argument("file")

    args = parser.parse_args(argv)

    import google.auth.exceptions
    from googleapiclient.errors import HttpError

    from .api import GDocsApi
    from .auth import get_credentials

    try:
        return _run(args, GDocsApi(get_credentials()))
    except HttpError as e:
        status = e.resp.status
        if status == 404:
            raise SystemExit(
                "Google Doc not found — it may have been deleted, or this "
                "account has no access to it."
            ) from e
        if status == 403:
            raise SystemExit(
                "Permission denied by Google. Check that the Docs and Drive APIs "
                "are enabled for your OAuth client and that this account can "
                "edit the document."
            ) from e
        raise SystemExit(f"Google API error ({status}): {e.reason}") from e
    except google.auth.exceptions.GoogleAuthError as e:
        raise SystemExit(
            f"Authentication failed: {e}. Delete the cached token "
            "(~/.config/md-gdoc/token.json) to re-authenticate."
        ) from e


def _run(args: argparse.Namespace, api: GDocsApi) -> int | None:
    if args.command == "push":
        from .push import push

        res = push(args.file, api, replace=args.replace, force=args.force, yes=args.yes)
        if res.state == "created":
            print(f"Created doc: {res.url}")
        elif res.state == "noop":
            print("No changes to push.")
        else:
            print(f"{res.state.capitalize()}: {res.url}")
            if res.orphaned:
                print(f"Orphaned {len(res.orphaned)} comment anchor(s).")
    elif args.command == "clone":
        from .clone import clone

        res = clone(args.url, args.file, api)
        if isinstance(res, list):
            for r in res:
                print(f"Cloned to {r.path}")
            first = res[0]
            from . import binding as _binding

            cf = _binding.comments_file(first.path.read_text(encoding="utf-8"))
            comments_path = (first.path.parent / cf) if cf else (str(first.path) + ".comments.md")
            print(f"{first.comment_count} comment(s) saved to {comments_path}")
        else:
            print(f"Cloned to {res.path}")
            print(f"{res.comment_count} comment(s) saved to {res.path}.comments.md")
    elif args.command == "pull":
        from .pull import pull

        res = pull(args.file, api)
        print(f"{res.comment_count} comment(s) pulled.")
        if res.state == "clean":
            print("No remote edits.")
        elif res.state == "updated":
            print("Remote edits applied to local file.")
        else:
            print(f"Both sides changed — remote copy written to {res.remote_path}.")
            print("Merge manually (or with your agent), then push.")
    elif args.command == "status":
        from .status import status

        res = status(args.file, api)
        print(res.url)
        print(f"Remote changes: {'yes' if res.remote_changed else 'no'}")
        print(f"Open comments: {res.open_comments}")
    return 0
