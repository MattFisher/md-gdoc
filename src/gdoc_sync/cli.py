"""gdoc-sync command line interface."""

import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gdoc-sync",
        description="Sync local markdown with Google Docs (push/pull/status).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push", help="create or update the Google Doc from the file")
    p_push.add_argument("file")
    p_push.add_argument("--replace", action="store_true",
                        help="re-import the whole doc (orphans ALL comment anchors)")
    p_push.add_argument("--force", action="store_true",
                        help="push even if the remote doc has unpulled changes")
    p_push.add_argument("--yes", action="store_true", help="skip confirmation prompts")

    p_pull = sub.add_parser("pull", help="fetch comments and remote edits")
    p_pull.add_argument("file")

    p_status = sub.add_parser("status", help="check for remote changes and open comments")
    p_status.add_argument("file")

    args = parser.parse_args(argv)

    from .api import GDocsApi
    from .auth import get_credentials

    api = GDocsApi(get_credentials())

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
    else:
        parser.error(f"unknown command {args.command!r}")
    return 0
