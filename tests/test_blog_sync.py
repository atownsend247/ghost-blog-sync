from datetime import datetime, timedelta, timezone

import pytest

from blog_sync import cli, commands, config as config_mod
from blog_sync.config import Config
from blog_sync.posts import content_hash, load_posts, read_banner, set_banner, to_html


class Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class FakeGhost:
    """Just enough of the Admin API: posts by slug, a scheduled-posts listing,
    and PUT recording."""

    def __init__(self, posts=None, scheduled_elsewhere=()):
        self.posts = posts or {}  # slug -> {status, published_at}
        self.scheduled_elsewhere = list(scheduled_elsewhere)  # published_at of other series' posts
        self.puts = []

    def get(self, url, params=None):
        if url.endswith("/posts/"):
            scheduled = [{"published_at": p["published_at"]} for p in self.posts.values() if p["status"] == "scheduled"]
            # The real API filters by tag; posts "elsewhere" belong to other series.
            if "tag:" not in (params or {}).get("filter", ""):
                scheduled += [{"published_at": d} for d in self.scheduled_elsewhere]
            return Resp(200, {"posts": scheduled})
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slug not in self.posts:
            return Resp(404)
        return Resp(200, {"posts": [{"id": slug, "updated_at": "u", "published_at": None, **self.posts[slug]}]})

    def put(self, url, json=None):
        body = json["posts"][0]
        self.puts.append((url.rstrip("/").rsplit("/", 1)[-1], body["published_at"]))
        return Resp(200)


def iso(days_ahead):
    return (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def make_posts(*slugs):
    return [{"number": i, "slug": s, "path": None, "title": s, "body_md": ""} for i, s in enumerate(slugs, 1)]


def write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


# -- config -------------------------------------------------------------


def test_config_resolves_dir_relative_to_the_config_file(tmp_path):
    (tmp_path / "posts").mkdir()
    write(tmp_path, "blog.toml", 'tag = "Building X"\ndir = "posts"\nslug_prefix = "x-"\n')
    config = config_mod.load(tmp_path / "blog.toml")
    assert config == Config(tag="Building X", posts_dir=(tmp_path / "posts").resolve(), slug_prefix="x-")
    assert config.tag_slug == "building-x"


def test_config_defaults_dir_to_the_config_files_own_folder(tmp_path):
    write(tmp_path, "blog.toml", 'tag = "T"\n')
    assert config_mod.load(tmp_path / "blog.toml").posts_dir == tmp_path.resolve()


@pytest.mark.parametrize("text", ['dir = "."\n', 'tag = ""\n', 'tag = "T"\nbogus = 1\n', "not toml ["])
def test_config_rejects_bad_files(tmp_path, text):
    write(tmp_path, "blog.toml", text)
    with pytest.raises(SystemExit):
        config_mod.load(tmp_path / "blog.toml")


def test_config_found_in_a_blog_subfolder(tmp_path, monkeypatch):
    (tmp_path / "blog").mkdir()
    write(tmp_path / "blog", "blog.toml", 'tag = "T"\n')
    monkeypatch.chdir(tmp_path)
    assert config_mod.load().posts_dir == (tmp_path / "blog").resolve()


# -- posts and links ----------------------------------------------------


def test_load_posts_numbers_titles_and_prefixes_slugs(tmp_path):
    write(tmp_path, "01-first.md", "# First post\n\nBody\n")
    write(tmp_path, "02-second.md", "# Second\n\nMore\n")
    write(tmp_path, "README.md", "# Index\n")
    posts = load_posts(Config(tag="T", posts_dir=tmp_path, slug_prefix="x-"))
    assert [(p["number"], p["slug"], p["title"]) for p in posts] == [(1, "x-first", "First post"), (2, "x-second", "Second")]


def test_post_without_a_title_is_an_error(tmp_path):
    write(tmp_path, "01-a.md", "no heading here\n")
    with pytest.raises(SystemExit):
        load_posts(Config(tag="T", posts_dir=tmp_path))


def test_links_between_posts_and_to_the_index_are_rewritten(tmp_path):
    write(tmp_path, "01-first.md", "# First\n")
    write(tmp_path, "02-second.md", "# Second\n")
    config = Config(tag="Building X", posts_dir=tmp_path, slug_prefix="x-")
    posts = load_posts(config)
    html = to_html("[a](01-first.md) [b](02-second.md#part) [i](README.md) [o](other.md)", config, posts)
    assert 'href="/x-first/"' in html
    assert 'href="/x-second/#part"' in html
    assert 'href="/tag/building-x/"' in html
    assert 'href="other.md"' in html  # not a post: left alone


def test_html_comments_are_stripped_and_hash_is_stable():
    config = Config(tag="T", posts_dir=None)
    html = to_html("Hi\n\n<!-- commits: abc -->\n", config, [])
    assert "commits" not in html
    assert content_hash("t", html) == content_hash("t", html) != content_hash("u", html)


def test_banner_round_trip():
    text = "# Title\n\nBody\n"
    with_banner = set_banner(text, "https://img/x.jpg", "alt text")
    assert read_banner(with_banner) == ("https://img/x.jpg", "alt text")
    assert read_banner(set_banner(with_banner, None, None)) == (None, None)
    assert set_banner(with_banner, None, None) == text


# -- scheduling ---------------------------------------------------------


def test_scheduling_starts_tomorrow_when_nothing_is_queued():
    ghost = FakeGhost({"a": {"status": "draft"}, "b": {"status": "draft"}})
    commands.schedule_drafts(ghost, "B", make_posts("a", "b"), 2, "09:00", apply=True, tag_slug="t")
    assert [slug for slug, _ in ghost.puts] == ["a", "b"]
    # Compared as London local times: the gap is two calendar days at 09:00
    # even when the clocks change in between.
    first, second = (
        datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(commands.PUBLISH_TZ) for _, d in ghost.puts
    )
    assert (second.date() - first.date(), first.hour, second.hour) == (timedelta(days=2), 9, 9)


def test_new_post_queues_behind_the_series_own_scheduled_posts():
    ghost = FakeGhost({"a": {"status": "scheduled", "published_at": iso(10)}, "b": {"status": "draft"}})
    commands.schedule_drafts(ghost, "B", make_posts("a", "b"), 2, "09:00", apply=True, tag_slug="t")
    (slug, when), = ghost.puts
    assert slug == "b"
    assert datetime.fromisoformat(when.replace("Z", "+00:00")) > datetime.now(timezone.utc) + timedelta(days=11)


def test_other_projects_scheduled_posts_do_not_push_this_series_back():
    # Another series on the same blog has a post going out in 20 days. This
    # series has its own cadence, so its first post still goes out tomorrow.
    ghost = FakeGhost({"a": {"status": "draft"}}, scheduled_elsewhere=[iso(20)])
    commands.schedule_drafts(ghost, "B", make_posts("a"), 2, "09:00", apply=True, tag_slug="t")
    (_, when), = ghost.puts
    assert datetime.fromisoformat(when.replace("Z", "+00:00")) < datetime.now(timezone.utc) + timedelta(days=2)


def test_scheduling_skips_posts_that_are_not_drafts_or_not_on_ghost(capsys):
    ghost = FakeGhost({"a": {"status": "published"}})
    commands.schedule_drafts(ghost, "B", make_posts("a", "missing"), 2, "09:00", apply=True, tag_slug="t")
    out = capsys.readouterr().out
    assert ghost.puts == []
    assert "[published, skipped]" in out and "[not on Ghost]" in out


def test_scheduling_is_a_dry_run_without_apply():
    ghost = FakeGhost({"a": {"status": "draft"}})
    commands.schedule_drafts(ghost, "B", make_posts("a"), 2, "09:00", apply=False, tag_slug="t")
    assert ghost.puts == []


# -- cli ----------------------------------------------------------------


def test_cli_without_credentials_just_lists_the_posts(tmp_path, monkeypatch, capsys):
    write(tmp_path, "blog.toml", 'tag = "T"\n')
    write(tmp_path, "01-first.md", "# First\n\nBody\n")
    monkeypatch.delenv("GHOST_URL", raising=False)
    monkeypatch.delenv("GHOST_ADMIN_KEY", raising=False)
    cli.main(["--config", str(tmp_path / "blog.toml")])
    assert "[dry-run] 01 first" in capsys.readouterr().out


def test_cli_apply_without_credentials_is_an_error(tmp_path, monkeypatch):
    write(tmp_path, "blog.toml", 'tag = "T"\n')
    monkeypatch.delenv("GHOST_URL", raising=False)
    monkeypatch.delenv("GHOST_ADMIN_KEY", raising=False)
    with pytest.raises(SystemExit):
        cli.main(["--config", str(tmp_path / "blog.toml"), "--apply"])
