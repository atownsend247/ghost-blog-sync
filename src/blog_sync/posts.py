"""Reading posts from disk and turning their markdown into Ghost-ready HTML."""
import hashlib
import re
import sys
from pathlib import Path

import markdown

POST_RE = re.compile(r"^(\d\d)-(.+)\.md$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)  # internal metadata (e.g. commits covered)
LINK_RE = re.compile(r'href="([^"#]+)\.md(#[^"]*)?"')
BANNER_RE = re.compile(r"\n<!-- banner: (\S+) -->\n")
BANNER_ALT_RE = re.compile(r"<!-- banner-alt: (.*?) -->\n")


def read_banner(text):
    """(url, alt) recorded in a post's markdown, either may be None."""
    url, alt = BANNER_RE.search(text), BANNER_ALT_RE.search(text)
    return (url.group(1) if url else None, alt.group(1) if alt else None)


def set_banner(text, url, alt):
    """`text` with its banner comments replaced (or removed when url is None),
    placed straight under the H1."""
    text = BANNER_ALT_RE.sub("", BANNER_RE.sub("", text))
    if not url:
        return text
    end = text.index("\n") + 1  # just the H1 line, not the blank lines after it
    block = f"\n<!-- banner: {url} -->\n" + (f"<!-- banner-alt: {alt} -->\n" if alt else "")
    return text[:end] + block + text[end:]


def load_posts(config):
    """Every NN-name.md in the posts dir, in number order. Anything else
    (README.md and so on) is not a post."""
    posts = []
    for path in sorted(config.posts_dir.glob("*.md")):
        m = POST_RE.match(path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        title_m = re.match(r"\s*#\s+(.+?)\s*\n", text)
        if not title_m:
            sys.exit(f"{path.name}: no H1 title found")
        posts.append({
            "number": int(m.group(1)),
            "slug": config.slug_prefix + m.group(2),
            "path": path,
            "title": title_m.group(1),
            "body_md": text[title_m.end():].lstrip("\n"),
        })
    return posts


def to_html(body_md, config, posts):
    """Markdown to HTML, with links between posts (`[x](02-foo.md)`) pointed at
    the posts' Ghost URLs and links to README.md pointed at the series' tag page.
    A link to a .md file that isn't a post is left alone."""
    html = markdown.markdown(COMMENT_RE.sub("", body_md), extensions=["fenced_code", "sane_lists"])
    slug_by_stem = {p["path"].stem: p["slug"] for p in posts}

    def fix_link(m):
        stem, anchor = Path(m.group(1)).name, m.group(2) or ""
        if stem == "README":
            return f'href="/tag/{config.tag_slug}/"'
        if stem in slug_by_stem:
            return f'href="/{slug_by_stem[stem]}/{anchor}"'
        return m.group(0)

    return LINK_RE.sub(fix_link, html)


def content_hash(title, html):
    return hashlib.sha256(f"{title}\n{html}".encode()).hexdigest()[:16]
