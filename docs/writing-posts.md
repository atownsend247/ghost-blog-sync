# Writing posts

## File names and order

A post is a markdown file named `NN-slug.md` in the posts folder: two digits, a
hyphen, then a slug of lowercase words joined by hyphens.

```
01-choosing-a-database.md      slug: choosing-a-database   (plus slug_prefix, if set)
02-first-prototype.md
```

Anything else in the folder (`README.md`, notes, images) is not a post and is
ignored. The number is the series order: it's the order posts are scheduled in
and listed in output. Posts load in file-name order, so keep two digits.

The first line must be a `# Title` heading. It becomes the post's title and is
removed from the body (Ghost shows the title itself). A file without one stops
the run with an error naming it.

## Links between posts

Write ordinary relative markdown links to the other files:

```markdown
Previous: [← The first prototype](02-first-prototype.md)
See [the index](README.md) or [part 3](03-storage.md#sqlite).
```

On the way to Ghost they become the site's real URLs:

| You write | Ghost gets |
|---|---|
| `[x](03-storage.md)` | `/<slug_prefix>storage/` |
| `[x](03-storage.md#sqlite)` | `/<slug_prefix>storage/#sqlite` |
| `[x](README.md)` | `/tag/<tag-slug>/` - the series' tag page |

A `.md` link to something that isn't a post is left as written, and the run
prints `UNRESOLVED LINKS` for that post so a typo is visible.

## Hidden comments

HTML comments are stripped before anything is sent, so they can carry notes that
never reach readers. The existing series use one to record which commits a post
covers:

```markdown
<!-- commits: dd47f2a c7b1307 -->
```

Two comments have a meaning to the tool (next section); everything else is
yours.

## Banner images

Banners are **owned by Ghost**: set the feature image in the Ghost editor, then
run `blog-sync --pull`. That records it in the markdown, straight under the
title:

```markdown
# My title

<!-- banner: https://images.example.com/photo.jpg -->
<!-- banner-alt: A description of the photo -->
```

Pull only edits your local files, and a normal sync never sends banners to
Ghost, so it can't overwrite one you set there. Run `--pull` before editing a
post's markdown so the record is current, and commit the result.

## What changing a post does

Edit the markdown and merge: the next sync updates the post on Ghost in place. A
published post stays published and a draft stays a draft. Only a change to the
**title or body** counts (banner and other comments don't), so adding a banner
comment never causes a re-publish. See [how it works](how-it-works.md).
