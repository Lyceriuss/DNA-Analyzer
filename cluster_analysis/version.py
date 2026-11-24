"""The app's version, shown in the page and compared with the update feed (DNA_UPDATE_URL). The knowledge bundle and the
references carry their own versions (knowledge.py, genome/references.json)."""
import json
import os
import urllib.request

VERSION = "0.1.9"
NAME = "DNA-Analyzer"   # until the product name is chosen


def _key(v):
    return tuple(int(x) if x.isdigit() else 0 for x in str(v).split("."))


def check(url=None, timeout=10):
    """{"current", "latest", "newer", "url", "notes"} from the update feed, or None without one. The feed is a small JSON
    file on our site ({"version", "windows", "linux", "sha256": {...}, "notes"}); asking for it sends nothing but the
    request itself."""
    url = url or os.environ.get("DNA_UPDATE_URL")
    if not url:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": f"{NAME}/{VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        feed = json.load(r)
    plat = "windows" if os.name == "nt" else "linux"
    return {"current": VERSION, "latest": feed.get("version"), "newer": _key(feed.get("version", "0")) > _key(VERSION),
            "url": feed.get(plat) or feed.get("page"), "sha256": (feed.get("sha256") or {}).get(plat), "notes": feed.get("notes")}
