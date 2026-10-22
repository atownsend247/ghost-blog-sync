"""Command-line entry point: `blog-sync [--apply | --pull | --schedule]`."""
import argparse
import os

from blog_sync import commands, config as config_mod, ghost
from blog_sync.posts import load_posts

DESCRIPTION = """Keep a folder of markdown posts in sync with a Ghost blog.

Dry-run unless --apply is passed. With no mode flag it syncs content: posts
missing on Ghost are created as drafts, changed ones updated in place (status
untouched), unchanged ones skipped. --pull and --schedule are separate modes.
Settings come from blog.toml (see --config); credentials from GHOST_URL and
GHOST_ADMIN_KEY ("id:secret")."""


def build_parser():
    ap = argparse.ArgumentParser(prog="blog-sync", description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="path to blog.toml (default: ./blog.toml, then ./blog/blog.toml)")
    ap.add_argument("--apply", action="store_true", help="write to Ghost (default: report only)")
    ap.add_argument("--pull", action="store_true", help="copy banner images from Ghost into the markdown (local edits only)")
    ap.add_argument("--schedule", action="store_true", help="schedule draft posts, one every --every days, queued after anything already scheduled")
    ap.add_argument("--every", type=int, default=2, help="days between scheduled posts (default 2)")
    ap.add_argument("--at", default="09:00", help="London time of day to publish, HH:MM (default 09:00)")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = config_mod.load(args.config)
    posts = load_posts(config)

    if args.pull:
        session, base = ghost.admin_session()
        commands.pull_banners(session, base, posts)
        return
    if args.schedule:
        session, base = ghost.admin_session()
        commands.schedule_drafts(session, base, posts, args.every, args.at, args.apply)
        return

    session = base = None
    if args.apply or (os.environ.get("GHOST_URL") and os.environ.get("GHOST_ADMIN_KEY")):
        session, base = ghost.admin_session()
    commands.sync(session, base, config, posts, args.apply)


if __name__ == "__main__":
    main()
