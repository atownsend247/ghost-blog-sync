# How it works

## Syncing content (`blog-sync --apply`)

For each post, in order, the tool asks Ghost for the post with that slug and
decides:

| Situation | Action |
|---|---|
| No post with that slug | **create** it as a draft, tagged with the series tag |
| Exists, content changed or tag missing | **update** it in place; status is left alone |
| Exists, content identical and tagged | skip (`unchanged`) |

Without `--apply` the same decisions are printed as `[dry-run: would create]`
etc. and nothing is written.

### Change detection

Ghost re-renders HTML it receives, so what comes back can't be compared with
what was sent. Instead the tool hashes the title plus the rendered HTML (16 hex
characters of SHA-256) and stores it in the post's *code injection header* as a
comment:

```html
<!-- blog-sync:3fa91c0e5b7d2a46 -->
```

Next run it renders the markdown again and compares hashes. Consequences:

- Editing the title or body changes the hash, so the post is updated.
- Editing only hidden comments (commit lists, banner records) doesn't, since
  comments are stripped before hashing.
- Changing the tool's HTML rendering (a new release that renders markdown
  differently) would change every hash and update every post once. Releases note
  when that happens.
- The header injection is the tool's. Don't edit it by hand in Ghost.

### What it never does

- It never changes a post's `published`/`draft`/`scheduled` status. New posts
  start as drafts; scheduling is a separate step.
- It never deletes anything. Removing a markdown file leaves the Ghost post.
- It never sends banner images, and never removes tags you added by hand.

## Scheduling (`blog-sync --schedule --apply`)

1. Ask Ghost for **every scheduled post on the blog** and take the latest date.
2. The first slot is the day after that, or tomorrow if nothing is scheduled,
   whichever is later. Times are London time (`--at`, default 09:00), converted
   to UTC for Ghost, so summer time is handled.
3. Walk this series' posts in number order. For each:
   - not on Ghost: reported (`run --apply first`), skipped;
   - not a draft (published or already scheduled): reported, skipped;
   - a draft: scheduled for the next slot, which then advances by `--every` days.

Because step 1 reads the existing queue, the command is **safe to re-run** on
every build: with nothing in draft it changes nothing, and a post added later
joins the back of the queue instead of jumping ahead of posts already waiting.
Because the queue is blog-wide, so do other projects' posts.

Scheduling runs separately from the content sync and must come second in a
pipeline: a post that isn't on Ghost yet can't be scheduled.

Putting a scheduled post back to draft in Ghost does **not** hold it. The next
run sees a draft and schedules it again. To hold a post back, don't merge it.

## Pulling banners (`blog-sync --pull`)

For each post, reads the feature image and alt text from Ghost and rewrites the
`<!-- banner: -->` / `<!-- banner-alt: -->` comments in the local file to match
(removing them if Ghost has none). Files already matching are untouched. It
never writes to Ghost.

## Errors

Any unexpected Ghost response (other than a 404 on a lookup, which means "not
there yet") stops the run with the HTTP status and the first 300 characters of
the body, and a non-zero exit status. Posts handled before the failure stay
handled; a re-run picks up where it left off, since every step is idempotent.
