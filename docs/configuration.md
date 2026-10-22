# Configuration

Each project has one small TOML file, `blog.toml`, next to its posts. It is found
automatically as `./blog.toml` or `./blog/blog.toml` (relative to where the tool
is run, normally the repo root), or pass `--config PATH`.

```toml
tag = "Building My Project"   # required
dir = "."                     # optional
slug_prefix = ""              # optional
```

Unknown keys are an error, so a typo doesn't silently do nothing.

| Setting | Required | Meaning |
|---|---|---|
| `tag` | yes | The Ghost tag every post in the series gets (created on Ghost if missing). Also decides the series' tag page, `/tag/<slug>/`, which links to `README.md` resolve to. A tag is added to a post that lacks it; tags you added by hand are kept. |
| `dir` | no | Folder holding the `NN-slug.md` files, **relative to the config file** (not to where you run the tool), so the same config works in a Jenkins workspace and on a laptop. Defaults to the config file's own folder. |
| `slug_prefix` | no | Text put in front of every post's slug. Default none. |

## Sharing one blog between projects

Everything below only matters when more than one project publishes to the same
Ghost site.

### Slugs must be unique across the blog

A post is matched to Ghost by its **slug**, which comes from the file name:
`01-introduction.md` becomes `introduction`. If two projects both have
`01-introduction.md`, the second one to sync **overwrites the first**.

Give each project a prefix:

```toml
tag = "Building Spoolman Bridge"
slug_prefix = "spoolman-"       # 01-introduction.md  ->  /spoolman-introduction/
```

Links between that project's posts (`[next](02-foo.md)`) are rewritten using the
prefixed slugs automatically.

Changing a prefix on a series that is already on Ghost makes every post look
new: it creates a second copy under the new slug and leaves the old one. Choose
the prefix before the first sync, or rename the old posts' slugs in Ghost.

### Scheduling queues across projects

`--schedule` starts the first post the day after the latest post scheduled
**anywhere on the blog**, not just in the current series. So two projects
scheduling in turn line up one after the other instead of both claiming
tomorrow. Only posts still in draft are scheduled; published and
already-scheduled posts are never touched.

The queue is read at the start of each run. Two runs at the same moment (two
projects' pipelines building together) can both read an empty queue and pick the
same day - see [locking in docs/jenkins.md](jenkins.md#avoiding-two-projects-scheduling-at-once).

### One credential pair for all of them

All projects use the same `GHOST_URL` and `GHOST_ADMIN_KEY`. In Jenkins, make
them global credentials so every project's job can use them.
