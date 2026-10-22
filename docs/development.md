# Development

```sh
uv sync                  # or: python -m venv .venv && .venv/bin/pip install -e . pytest
uv run pytest
uv run blog-sync --config path/to/blog.toml     # dry run against a project's posts
```

The tests use a small fake of the Ghost Admin API (`FakeGhost` in
`tests/test_blog_sync.py`), so they need no credentials or network. They cover
config parsing, slug prefixes, link rewriting, banner round-trips, and the
scheduling rules (including ignoring other projects' scheduled posts).

## Layout

| File | Responsibility |
|---|---|
| `src/blog_sync/config.py` | find and validate `blog.toml` |
| `src/blog_sync/posts.py` | read `NN-slug.md` files, markdown to HTML, link rewriting, content hash, banner comments |
| `src/blog_sync/ghost.py` | Admin API auth (JWT from `GHOST_ADMIN_KEY`) |
| `src/blog_sync/commands.py` | sync, pull banners, schedule |
| `src/blog_sync/cli.py` | argument parsing and dispatch |

## Releasing

Projects pin a tag, so a release is: update the version in `pyproject.toml`,
commit, `git tag vX.Y.Z`, push both. Bump each project's `@vX.Y.Z` when you want
it on the new version.

Be careful with any change to how markdown is rendered to HTML: it alters the
content hash, which makes every existing post look changed and re-updates all of
them on the next run (harmless, but noisy). Say so in the release notes.
