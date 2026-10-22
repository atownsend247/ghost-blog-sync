"""Per-project settings, read from a small blog.toml next to the posts."""
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Looked for, in order, relative to the directory the tool is run from.
DEFAULT_LOCATIONS = ("blog.toml", "blog/blog.toml")
_KNOWN_KEYS = {"tag", "dir", "slug_prefix"}


@dataclass(frozen=True)
class Config:
    tag: str  # Ghost tag every post of this series carries
    posts_dir: Path  # where the NN-slug.md files live
    slug_prefix: str = ""  # prepended to every post's slug (see docs/configuration.md)

    @property
    def tag_slug(self):
        """The tag's URL slug, as Ghost derives it: lower-cased, spaces to hyphens."""
        return re.sub(r"[^a-z0-9]+", "-", self.tag.lower()).strip("-")


def find(path=None):
    if path:
        return Path(path)
    for candidate in DEFAULT_LOCATIONS:
        if Path(candidate).is_file():
            return Path(candidate)
    sys.exit(f"No config found - pass --config, or create one of: {', '.join(DEFAULT_LOCATIONS)}")


def load(path=None):
    path = find(path)
    if not path.is_file():
        sys.exit(f"Config file not found: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        sys.exit(f"{path}: invalid TOML - {exc}")

    unknown = set(data) - _KNOWN_KEYS
    if unknown:
        sys.exit(f"{path}: unknown setting(s) {sorted(unknown)} (known: {sorted(_KNOWN_KEYS)})")
    tag = data.get("tag")
    if not isinstance(tag, str) or not tag.strip():
        sys.exit(f"{path}: 'tag' is required (the Ghost tag every post in this series gets)")

    # `dir` is relative to the config file, not to wherever the tool was run
    # from, so the same file works from a Jenkins workspace and a laptop.
    posts_dir = (path.parent / data.get("dir", ".")).resolve()
    if not posts_dir.is_dir():
        sys.exit(f"{path}: dir {posts_dir} does not exist")
    return Config(tag=tag.strip(), posts_dir=posts_dir, slug_prefix=data.get("slug_prefix", ""))
