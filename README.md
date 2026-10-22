# blog-sync

Keep a folder of markdown posts in sync with a [Ghost](https://ghost.org) blog
through the Admin API. The markdown is the source of truth: write a post, merge
it, and a pipeline creates it on Ghost as a draft, keeps it up to date, and
(optionally) schedules it to go live.

```
my-project/
└── blog/
    ├── blog.toml            # tag = "Building My Project"
    ├── 01-why-i-built-it.md
    ├── 02-first-prototype.md
    └── README.md            # series index (not a post)
```

## What it does

| Mode | Command | Effect |
|---|---|---|
| Sync content *(default)* | `blog-sync --apply` | Creates posts missing on Ghost as **drafts**; updates changed ones in place; skips unchanged ones. A post's published/draft status is never changed. |
| Schedule | `blog-sync --schedule --apply` | Schedules this series' posts still in draft, one every other day at 09:00 London time, queued **after this series' last scheduled post** (other projects on the blog don't affect it). |
| Pull banners | `blog-sync --pull` | Copies banner images you set in Ghost's editor back into the markdown. Edits local files only. |

Every mode is a **dry run unless `--apply` is passed** (`--pull` always only
edits local files). With no credentials set, the default mode just lists the
posts it found.

## Install and run

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/). Nothing to install in
your project: run it straight from this repo, pinned to a tag.

```sh
export GHOST_URL=https://blog.example.com
export GHOST_ADMIN_KEY=<id>:<secret>      # Ghost Admin → Settings → Integrations

uvx --from git+https://github.com/atownsend247/ghost-blog-sync.git@v0.1.0 blog-sync                 # list / dry run
uvx --from git+https://github.com/atownsend247/ghost-blog-sync.git@v0.1.0 blog-sync --apply         # sync content
uvx --from git+https://github.com/atownsend247/ghost-blog-sync.git@v0.1.0 blog-sync --schedule --apply
```

Or from a local checkout while developing: `uv run blog-sync --config path/to/blog.toml`.

Credentials come from environment variables only; the tool never reads or
writes them anywhere else.

## Setting up a project

1. Add `blog/blog.toml` (or `blog.toml` at the repo root):
   ```toml
   tag = "Building My Project"
   ```
2. Add posts named `NN-slug.md` (`01-intro.md`), each starting with a `# Title`
   line. See [docs/writing-posts.md](docs/writing-posts.md).
3. Run `blog-sync` to check the posts are found, then add the pipeline stage
   from [docs/jenkins.md](docs/jenkins.md).

If the project shares a blog with others, read the
[sharing a blog](docs/configuration.md#sharing-one-blog-between-projects) notes
first (slug prefixes).

## Documentation

- [docs/configuration.md](docs/configuration.md) - `blog.toml` settings, and sharing one blog between projects
- [docs/writing-posts.md](docs/writing-posts.md) - file naming, links between posts, banners, hidden comments
- [docs/how-it-works.md](docs/how-it-works.md) - change detection, status handling, scheduling rules
- [docs/jenkins.md](docs/jenkins.md) - the pipeline stage, credentials
- [docs/migrating-from-ghost-publish.md](docs/migrating-from-ghost-publish.md) - moving a project off the copied `ghost_publish.py`
- [docs/development.md](docs/development.md) - tests and releasing

## Command reference

```
blog-sync [--config PATH] [--apply] [--pull] [--schedule] [--every N] [--at HH:MM]
```

| Flag | Default | Meaning |
|---|---|---|
| `--config PATH` | `./blog.toml`, then `./blog/blog.toml` | Settings file |
| `--apply` | off | Write to Ghost (otherwise report only) |
| `--pull` | off | Banner images from Ghost into the markdown |
| `--schedule` | off | Schedule draft posts instead of syncing content |
| `--every N` | 2 | Days between scheduled posts |
| `--at HH:MM` | 09:00 | London time of day posts go out |

Exit status is non-zero on any Ghost API error, or a missing/invalid config.
