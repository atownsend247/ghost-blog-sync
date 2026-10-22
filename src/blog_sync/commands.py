"""The three things the tool does: sync content, pull banners, schedule drafts."""
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from blog_sync.posts import content_hash, read_banner, set_banner, to_html

SYNC_RE = re.compile(r"<!-- blog-sync:([0-9a-f]{16}) -->")
PUBLISH_TZ = ZoneInfo("Europe/London")


def _plan(session, base, config, post, html):
    """(action, existing) where action is create/update/unchanged."""
    r = session.get(
        f"{base}/posts/slug/{post['slug']}/",
        params={"fields": "id,status,updated_at,codeinjection_head", "include": "tags"},
    )
    if r.status_code == 404:
        return "create", None
    if r.status_code != 200:
        sys.exit(f"lookup failed for {post['slug']}: HTTP {r.status_code}")
    existing = r.json()["posts"][0]
    m = SYNC_RE.search(existing.get("codeinjection_head") or "")
    has_tag = any(tag["name"] == config.tag for tag in existing.get("tags", []))
    if m and m.group(1) == content_hash(post["title"], html) and has_tag:
        return "unchanged", existing
    return "update", existing


def sync(session, base, config, posts, apply):
    """Create missing posts as drafts and update changed ones in place, leaving
    a post's published/draft status alone. With no session (no credentials)
    it only lists the posts; without `apply` it reports what would change."""
    counts = {}
    for p in posts:
        html = to_html(p["body_md"], config, posts)
        leftover = re.findall(r'href="([^"]+\.md[^"]*)"', html)
        note = f"  UNRESOLVED LINKS: {leftover}" if leftover else ""
        label = f"{p['number']:02d} {p['slug']:<45} {len(html):>6} chars  {p['title']!r}"

        if session is None:
            print(f"[dry-run] {label}{note}")
            continue

        action, existing = _plan(session, base, config, p, html)
        counts[action] = counts.get(action, 0) + 1
        if action == "unchanged":
            print(f"[unchanged] {label}{note}")
            continue
        if not apply:
            status = f" ({existing['status']})" if existing else ""
            print(f"[dry-run: would {action}{status}] {label}{note}")
            continue

        body = {
            "title": p["title"],
            "html": html,
            "codeinjection_head": f"<!-- blog-sync:{content_hash(p['title'], html)} -->",
        }
        if action == "create":
            body.update(slug=p["slug"], status="draft", tags=[{"name": config.tag}])
            r = session.post(f"{base}/posts/?source=html", json={"posts": [body]})
            ok = 201
        else:
            body["updated_at"] = existing["updated_at"]
            # Only add our tag when missing, so tags added by hand survive.
            if not any(tag["name"] == config.tag for tag in existing.get("tags", [])):
                body["tags"] = [*({"id": tag["id"]} for tag in existing.get("tags", [])), {"name": config.tag}]
            r = session.put(f"{base}/posts/{existing['id']}/?source=html", json={"posts": [body]})
            ok = 200
        if r.status_code != ok:
            sys.exit(f"{action} failed for {p['slug']}: HTTP {r.status_code} {r.text[:300]}")
        verb = "created draft" if action == "create" else f"updated ({existing['status']})"
        print(f"[{verb}] {label}{note}")

    if counts:
        print("summary:", ", ".join(f"{n} {a}" for a, n in sorted(counts.items())))


def pull_banners(session, base, posts):
    """Make each post's recorded banner match Ghost's. Local files only."""
    changed = 0
    for p in posts:
        r = session.get(f"{base}/posts/slug/{p['slug']}/", params={"fields": "feature_image,feature_image_alt"})
        if r.status_code == 404:
            print(f"[not on Ghost] {p['number']:02d} {p['slug']}")
            continue
        if r.status_code != 200:
            sys.exit(f"lookup failed for {p['slug']}: HTTP {r.status_code}")
        remote = r.json()["posts"][0]
        url, alt = remote.get("feature_image") or None, remote.get("feature_image_alt") or None
        text = p["path"].read_text(encoding="utf-8")
        if read_banner(text) == (url, alt):
            continue
        p["path"].write_text(set_banner(text, url, alt), encoding="utf-8")
        changed += 1
        print(f"[banner {'set' if url else 'removed'}] {p['number']:02d} {p['slug']}  {url or ''}")
    print(f"summary: {changed} markdown file(s) updated from Ghost banners")


def _last_scheduled_date(session, base, tag_slug):
    """The London date of the latest post of this series (the posts carrying
    `tag_slug`) that is scheduled, or None if there isn't one. Other projects'
    scheduled posts are ignored, so each series keeps its own cadence."""
    r = session.get(
        f"{base}/posts/",
        params={"filter": f"status:scheduled+tag:{tag_slug}", "fields": "published_at", "limit": "all"},
    )
    if r.status_code != 200:
        sys.exit(f"could not list scheduled posts: HTTP {r.status_code}")
    dates = [
        datetime.fromisoformat(post["published_at"].replace("Z", "+00:00")).astimezone(PUBLISH_TZ).date()
        for post in r.json()["posts"]
        if post.get("published_at")
    ]
    return max(dates, default=None)


def schedule_drafts(session, base, posts, every, at, apply, tag_slug):
    """Schedule this series' draft posts in series order, one every `every`
    days. The first goes out `every` days after the latest post of this series
    already scheduled, or tomorrow if none is - so re-running is safe and a post
    added later queues up behind the earlier ones. Other series on the blog are
    not considered: each project runs on its own cadence."""
    hour, minute = (int(x) for x in at.split(":"))
    day = datetime.now(PUBLISH_TZ).date() + timedelta(days=1)
    last = _last_scheduled_date(session, base, tag_slug)
    if last is not None:
        day = max(day, last + timedelta(days=every))

    scheduled = 0
    for p in posts:
        r = session.get(f"{base}/posts/slug/{p['slug']}/", params={"fields": "id,status,updated_at,published_at"})
        if r.status_code == 404:
            print(f"[not on Ghost] {p['number']:02d} {p['slug']}  (run --apply first)")
            continue
        if r.status_code != 200:
            sys.exit(f"lookup failed for {p['slug']}: HTTP {r.status_code}")
        remote = r.json()["posts"][0]
        if remote["status"] != "draft":
            print(f"[{remote['status']}, skipped] {p['number']:02d} {p['slug']}")
            continue
        when = datetime(day.year, day.month, day.day, hour, minute, tzinfo=PUBLISH_TZ)
        label = f"{p['number']:02d} {p['slug']}  {when:%a %d %b %Y %H:%M %Z}"
        if apply:
            body = {
                "status": "scheduled",
                "published_at": when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "updated_at": remote["updated_at"],
            }
            r = session.put(f"{base}/posts/{remote['id']}/", json={"posts": [body]})
            if r.status_code != 200:
                sys.exit(f"schedule failed for {p['slug']}: HTTP {r.status_code} {r.text[:300]}")
            print(f"[scheduled] {label}")
        else:
            print(f"[dry-run: would schedule] {label}")
        scheduled += 1
        day += timedelta(days=every)
    print(f"summary: {scheduled} post(s) {'scheduled' if apply else 'would be scheduled'}")
