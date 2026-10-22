# Blog automation: Markdown to Ghost on every merge - Part 1

*~9 min read*

Every project I build gets a blog series. The
[finance system](https://github.com/atownsend247/finance-system) has nineteen
posts, the identity system has seven, and each one is a markdown file that sits
in the repo next to the code it describes. That part is easy to love: the posts
are diffable, they live in git, and I can write them in the same editor as the
code. The part I got tired of was the other half - copying each post into Ghost,
fixing the links by hand, setting a publish date, and then doing it all over
again when I corrected a typo.

This post is about the tool that removed that half: `blog-sync`. A merge to
`main` now creates the post on Ghost as a draft, keeps it up to date when I edit
it, and queues it to go live a couple of days later. It started life as a script
inside finance-system and became a shared package once a second project wanted
the same thing, so most of what follows is about the decisions that made it safe
to run on every single build.

## The shape of the problem

The requirements were short, and each one ruled something out:

- **Markdown is the source of truth.** Ghost is where posts are *published*, not
  where they're written. If I edit a post in the repo, Ghost should follow.
- **Safe to run every build.** I didn't want a "did the blog change?" condition in
  the Jenkinsfile. If running it twice is harmless, I can run it always.
- **Never surprise a reader.** A sync must not publish, unpublish or delete
  anything on its own.
- **Never block a deploy.** The blog is the least important thing a pipeline
  does. If Ghost is down, the app should still ship.

Almost every design choice below is one of those four, applied.

## One folder, one small config file

A project's series is a folder of files named `NN-slug.md`, plus a `blog.toml`:

```
blog/
├── blog.toml
├── 01-why-i-built-it.md
├── 02-first-prototype.md
└── README.md          # series index, not a post
```

```toml
tag = "Building Finance System"
```

The number is the series order, the rest is the slug, and the first line of the
file is the `# Title`. Anything that doesn't match the `NN-name.md` pattern -
the README, notes, images - is quietly ignored, so the folder can hold what it
likes. The tag is the one required setting: every post in the series gets it,
which gives each series its own tag page on the blog. Unknown keys in
`blog.toml` are an error, so a typo fails loudly instead of doing nothing.

## Making re-running safe: hash the thing you sent

The core loop is simple. For each post, ask Ghost for the post with that slug:

| Situation | Action |
|---|---|
| No post with that slug | create it as a **draft**, tagged with the series tag |
| Exists, content changed | update it in place, status left alone |
| Exists, content identical | skip |

The interesting question is "content changed". You can't compare what Ghost
returns with what you sent, because Ghost re-renders HTML it receives - the bytes
that come back are never the bytes that went in. So the tool doesn't try. It
renders the markdown, hashes the title plus the HTML, and stores the first 16
characters of the SHA-256 on the post itself, as a comment in its code
injection header:

```python
def content_hash(title, html):
    return hashlib.sha256(f"{title}\n{html}".encode()).hexdigest()[:16]
```

```html
<!-- blog-sync:3fa91c0e5b7d2a46 -->
```

Next run it renders again and compares hashes. Same hash and the right tag means
`[unchanged]` and no write at all, so a build where I changed nothing makes one
read request per post and nothing else. A useful side effect: the hash only
covers the *rendered* content, and HTML comments are stripped before rendering.
That means the hidden comments I use to note which commits a post covers - or
the banner records, which I'll get to - can change freely without ever causing a
re-publish.

Updating is careful about what it touches. It sends Ghost the post's
`updated_at` so a concurrent edit in the editor produces an error rather than a
silent overwrite, and it only adds the series tag when it's missing, so tags I
added by hand survive.

## The things it refuses to do

This is the list I'm most glad I wrote down before writing any code:

- It **never changes a post's status.** New posts are drafts. A published post
  stays published through any number of edits, and a draft stays a draft.
- It **never deletes anything.** Remove a markdown file and the Ghost post stays.
- It **never sends banner images**, and never removes tags I added by hand.

Each is a trade of convenience for safety. Not deleting means a renamed post can
leave an orphan behind that I tidy up manually. That's a small, visible,
recoverable cost; the alternative is a pipeline that can delete published
posts if I fat-finger a filename. And every mode is a **dry run unless `--apply`
is passed**, so `blog-sync` on its own just prints what it would do. With no
credentials set at all it simply lists the posts it found, which makes it a
handy way to check a new series is wired up correctly before anything touches
Ghost.

## Links, and where the banners live

Posts link to each other with ordinary relative markdown, which works in the
repo and on GitHub:

```markdown
Previous: [← The first prototype](02-first-prototype.md)
```

On the way to Ghost, the tool rewrites those links using the slug map it already
has: `03-storage.md` becomes `/storage/`, anchors included, and a link to
`README.md` becomes the series' tag page. A link to some other `.md` file is left
alone, and the run prints `UNRESOLVED LINKS` against that post, so a typo shows
up in the build output instead of as a 404 on the live site.

Banner images go the other way. I pick a feature image in Ghost's editor - it
has the Unsplash picker built in, and that's genuinely nicer than hunting for a
URL - and `blog-sync --pull` copies it back into the markdown as a hidden
comment under the title:

```markdown
<!-- banner: https://images.unsplash.com/photo-... -->
<!-- banner-alt: A description of the photo -->
```

Ghost owns the banner, the repo keeps a record of it, and a normal sync never
sends banners *to* Ghost, so it can't overwrite one I set by hand. `--pull` only
ever edits local files, which is why it isn't in the pipeline: a build shouldn't
commit to `main`, and the workspace gets wiped afterwards anyway. I run it by
hand before editing a post, and commit the result.

## Scheduling: the part that makes it feel automatic

Creating drafts is useful. Scheduling them is what turned it from "saves me
copying" into "I merge a post and forget about it". `blog-sync --schedule
--apply` works like this:

1. Ask Ghost for every scheduled post **on the whole blog** and take the latest
   date.
2. The first slot is the day after that, or tomorrow if nothing is queued.
3. Walk the series in number order. A draft gets the next slot - 09:00 London
   time by default, one post every other day - and the slot advances. Anything
   already published or scheduled is skipped, and anything not yet on Ghost is
   reported rather than guessed at.

Because step 1 reads the existing queue, the command is idempotent in exactly
the way the sync is: with nothing in draft it changes nothing, and a post I add
later joins the back of the queue rather than jumping ahead of ones already
waiting. Times are converted from London time to UTC for Ghost, so summer time
looks after itself.

The trade-off is that scheduling is *blind to intent*. If I put a scheduled post
back to draft in Ghost, the next build sees a draft and schedules it again. To
hold a post back, the rule is simply: don't merge it. That's a deliberate
simplification - git is the single place where "this is ready" gets decided.

The blog-wide queue matters because more than one project publishes to the same
Ghost site. If scheduling only looked at its own series, two projects would both
claim tomorrow. Reading the whole blog makes them line up one after another.

## The pipeline stage

The Jenkins side is one stage, after deploy:

```groovy
stage('Sync blog') {
    when { branch 'main' }
    steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
            withCredentials([
                string(credentialsId: 'ghost-url', variable: 'GHOST_URL'),
                string(credentialsId: 'ghost-admin-key', variable: 'GHOST_ADMIN_KEY'),
            ]) {
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

Every line of that is one of the four requirements:

- `when { branch 'main' }` - feature branches never touch the blog.
- `catchError(... UNSTABLE)` - a Ghost outage, an expired key or a typo in a post
  turns the build yellow rather than red, and the deploy that already ran is
  unaffected. The stage also comes *after* deploy for the same reason.
- `run_blog --apply` before `run_blog --schedule --apply` - order matters, since
  scheduling skips posts that aren't on Ghost yet, and Jenkins' default `sh -e`
  stops before the second command if the first fails.
- `@v0.1.0` - the tool is pinned to a release tag, so a change to blog-sync can
  never break a project's build until I bump that project's tag. I'd avoid
  `@main` here.
- No `changeset` condition - because unchanged posts are skipped, running it every
  build is cheap, and it also notices edits made in Ghost's editor.

`uvx` fetches and runs the tool straight from git, so there's nothing to install
in the project: no `requirements.txt` entry, no virtualenv, no vendored script.
The agent just needs `uv` and `git`. The Admin API credentials are two Jenkins
secret-text credentials at global scope, so every project's job can use the same
pair, and they come from the environment only - the tool never reads or writes
them anywhere else.

## From one project's script to a shared package

The first version of this was `blog/tools/ghost_publish.py`, living inside
finance-system and growing one flag at a time: first publishing, then banners,
then the scheduler, then the pipeline stage. It worked, and it was the right
place to start, because I didn't know what the tool needed to be until I'd used
it on a real series.

The trigger for extracting it was the identity system getting its own blog. The
alternatives were copying the script (and then fixing every bug twice), or making
it a package. Doing it properly meant a few things the script had quietly
assumed:

- **The tag was hard-coded**, so it became a `tag` setting in `blog.toml`.
- **Slugs came straight from file names**, which is fine for one series and a
  silent overwrite for two: if both projects have a `01-introduction.md`, the
  second sync clobbers the first. Hence the optional `slug_prefix` - the identity
  system's posts use `identity-system-`. The catch is that changing a prefix on
  a series already on Ghost makes every post look new, so it has to be chosen
  before the first sync. That's why finance-system leaves it unset: its posts
  were already live.
- **The scheduling queue was per series**, and became blog-wide, for the reason
  above.

Moving finance-system over was designed to be invisible. The file names, slugs
and hash are unchanged, so the first run after the switch should report every
post as `[unchanged]` and write nothing - and that's the parity check I ran
locally, as a dry run against the live blog, before touching the Jenkinsfile. If
anything had come back as an update, that would have been a difference to
understand rather than a thing to ship. Only then did I swap the pipeline's
commands, delete the copied script, and update the docs that told me to run
`hatch run blog:publish`.

## What it still doesn't do

A few honest gaps, because they shape how I use it:

- **There's a small race.** `disableConcurrentBuilds()` stops two builds of the
  same job overlapping, not builds of different projects. Two projects syncing at
  the same instant can both read the queue before either writes it, and both pick
  the same day. The cost is two posts on one day. The fix is a shared lock
  (the Lockable Resources plugin) around the stage, and I haven't needed it yet.
- **It's one-way, mostly.** Content flows from the repo to Ghost; only banners
  come back, and only when I ask. If I edit a post's body in Ghost's editor,
  the next sync will put the markdown version back - which is the point of
  markdown being the source of truth, but worth remembering.
- **A rendering change touches every post.** Because the hash covers rendered
  HTML, a release that renders markdown differently would update every post once
  on the next run. It's harmless, but it's the reason releases are pinned and
  noted.

## What this adds up to

None of the pieces is clever. A filename convention, a hash stored on the post, a
schedule that reads the queue before it writes, and a pipeline stage that can't
fail the build. But together they change the shape of writing: finishing a post
is now `git merge`, and the thing I used to do by hand - a dozen clicks, a date
picker, and a link check - happens on its own, a couple of days later, at 09:00.
That's the bar for tooling like this: not that it does something impressive, but
that I stop thinking about it.

---

<!-- commits: a5aec24 (blog-sync); finance-system ee1fcf0 f877107 a596afe f744640 f1c03fa; identity-system a4e547b -->
