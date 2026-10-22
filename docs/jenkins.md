# Running it from Jenkins

Add one stage to a project's `Jenkinsfile`, after the deploy stage so a blog
problem can never hold up shipping the app.

```groovy
stage('Sync blog') {
    when { branch 'main' }
    steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
            withCredentials([
                string(credentialsId: 'ghost-url', variable: 'GHOST_URL'),
                string(credentialsId: 'ghost-admin-key', variable: 'GHOST_ADMIN_KEY'),
            ]) {
                // The sync must come first: --schedule skips posts that
                // aren't on Ghost yet. Jenkins' default `sh -e` stops before
                // scheduling if the sync fails.
                sh '''
                    run_blog() {
                        uvx --from git+https://github.com/atownsend247/ghost-blog-sync.git@v0.1.0 blog-sync "$@"
                    }
                    run_blog --apply
                    run_blog --schedule --apply
                '''
            }
        }
    }
}
```

Drop the `--schedule` line to sync content without ever scheduling anything; the
posts then sit as drafts on Ghost until you publish them by hand.

## Why it looks like this

- **`when { branch 'main' }`** - only the main branch publishes. Feature
  branches never touch the blog.
- **`catchError(... UNSTABLE)`** - a Ghost outage, a bad key or a typo in a post
  marks the build yellow, not red, and the deploy that already ran is
  unaffected.
- **`@v0.1.0`** - pin a release tag. A change to blog-sync can then never break
  a project's build until you bump that project's tag. Avoid `@main`.
- **No `changeset` condition** - the tool skips unchanged posts, so running it
  every build is cheap, and it also notices edits made in Ghost's editor.
- **Don't run `--pull` in CI.** It rewrites local markdown, which the pipeline's
  `cleanWs()` would discard, and a build shouldn't commit to `main`. Run it by
  hand before editing a post, and commit the banner comments it records.

The agent needs [uv](https://docs.astral.sh/uv/) and `git` on its `PATH`. If it
doesn't already have uv, the existing finance-system pipeline installs it in an
`Install uv` stage with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## Credentials

Create two **Secret text** credentials with exactly these IDs, at **global**
scope so every project's job can use them:

| ID | Value |
|---|---|
| `ghost-url` | `https://blog.example.com` |
| `ghost-admin-key` | The `id:secret` Admin API key of a custom integration (Ghost Admin → Settings → Integrations → Add custom integration) |

Both are masked in build logs by `withCredentials`.

## Checking it worked

A first run with nothing to do prints `[unchanged]` for each post and
`summary: N unchanged`. A run that scheduled something prints `[scheduled] 04
some-slug  Tue 03 Nov 2026 09:00 GMT`. To preview without writing, run the same
commands locally without `--apply`.
