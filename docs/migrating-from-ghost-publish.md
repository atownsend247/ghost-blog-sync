# Moving a project off the copied `ghost_publish.py`

For a project that currently carries its own `blog/tools/ghost_publish.py`
(finance-system is the first one).

The posts and their Ghost counterparts don't change: same file names, same
slugs, same change-detection hash, so after the switch every post reports
`unchanged` and nothing is rewritten.

1. **Publish blog-sync** somewhere Jenkins can fetch it, and tag a release
   (`git tag v0.1.0 && git push --tags`).

2. **Add the config.** The old script hard-coded the tag, so write it down:
   ```toml
   # blog/blog.toml
   tag = "Building Finance System"
   ```
   Leave `slug_prefix` unset for a series already on Ghost: adding one would
   create duplicates (see [configuration](configuration.md#slugs-must-be-unique-across-the-blog)).

3. **Check parity locally** before touching the pipeline:
   ```sh
   export GHOST_URL=... GHOST_ADMIN_KEY=...
   uvx --from git+<repo>@v0.1.0 blog-sync          # dry run, reads Ghost
   ```
   Every post should print `[unchanged]`. Anything else is a difference to
   understand first.

4. **Swap the pipeline's commands** for the `run_blog` form in
   [jenkins.md](jenkins.md). The credentials stay the same
   (`ghost-url`, `ghost-admin-key`).

5. **Delete** `blog/tools/ghost_publish.py`, and the `[tool.hatch.envs.blog]`
   section in `pyproject.toml` if nothing else uses it.

6. Update any project docs that tell people to run
   `hatch run blog:publish` / `blog:schedule` to use `blog-sync`.

## What changed in behaviour

| | Old script | blog-sync |
|---|---|---|
| Tag | hard-coded | `tag` in `blog.toml` |
| Posts folder | the script's parent folder | `dir` in `blog.toml` (default: the config's folder) |
| `--schedule` queue | after the last scheduled post **in this series** | after the last scheduled post **on the whole blog** |
| Slugs | file name | file name, with optional `slug_prefix` |
| Flags | `--apply --pull --schedule --every --at` | same, plus `--config` |
