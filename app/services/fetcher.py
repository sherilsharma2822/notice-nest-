"""Find notices and download them, politely.

Politeness rules built in: obey robots.txt, identify ourselves in the User-Agent,
wait between requests, set time limits and a size limit.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from ..config import Config
from .regex_extractor import find_dates

log = logging.getLogger(__name__)

_robots_cache: dict[str, RobotFileParser | None] = {}
_last_request_at = 0.0
_VAGUE_TITLES = {"download", "click here", "view", "pdf", "link", "here", "read more", "details"}


@dataclass
class RawNotice:
    title: str
    url: str | None
    published: str | None = None      # ISO date
    text: str | None = None           # filled in for local (sample) notices


class FetchError(Exception):
    pass


# ---------------------------------------------------------------------------
# Polite HTTP
# ---------------------------------------------------------------------------
def robots_allowed(url: str) -> bool:
    parts = urlparse(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in _robots_cache:
        parser = RobotFileParser()
        parser.set_url(root + "/robots.txt")
        try:
            parser.read()
            _robots_cache[root] = parser
        except Exception:
            _robots_cache[root] = None        # robots.txt unreachable: treat as allowed
    parser = _robots_cache[root]
    return True if parser is None else parser.can_fetch(Config.user_agent(), url)


def polite_get(url: str) -> requests.Response | None:
    """Download a URL, or return None if not allowed / failed."""
    global _last_request_at
    if not robots_allowed(url):
        log.warning("robots.txt does not allow fetching %s - skipped.", url)
        return None
    wait = Config.REQUEST_DELAY_SECONDS - (time.time() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.get(url, headers={"User-Agent": Config.user_agent()},
                            timeout=Config.REQUEST_TIMEOUT_SECONDS)
        _last_request_at = time.time()
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Could not fetch %s (%s).", url, exc.__class__.__name__)
        return None
    if len(resp.content) > Config.MAX_DOWNLOAD_BYTES:
        log.warning("%s is larger than the size limit - skipped.", url)
        return None
    return resp


def looks_like_pdf(resp: requests.Response) -> bool:
    return resp.content[:4] == b"%PDF" or "pdf" in resp.headers.get("Content-Type", "").lower()


# ---------------------------------------------------------------------------
# Source kind: html_list (a real website)
# ---------------------------------------------------------------------------
def fetch_html_list(cfg: dict) -> list[RawNotice]:
    resp = polite_get(cfg["url"])
    if resp is None:
        raise FetchError(f"Could not load the notice list page: {cfg['url']}")
    soup = BeautifulSoup(resp.text, "html.parser")

    item_selector = (cfg.get("item_selector") or "").strip()
    link_selector = (cfg.get("link_selector") or "a").strip()
    date_selector = (cfg.get("date_selector") or "").strip()
    must_contain = [w.lower() for w in cfg.get("link_must_contain", []) or []]
    title_from = cfg.get("title_from", "link_text")

    items = soup.select(item_selector) if item_selector else [soup]
    notices, seen_urls = [], set()
    for item in items:
        for link in item.select(link_selector):
            href = (link.get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            full_url = urljoin(cfg["url"], href)
            if must_contain and not any(w in full_url.lower() for w in must_contain):
                continue
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = link.get_text(" ", strip=True)
            if title_from == "item_text" or len(title) < 8 or title.lower() in _VAGUE_TITLES:
                title = item.get_text(" ", strip=True) if item is not soup else title
            title = re.sub(r"\s+", " ", title)[:200] or "Untitled notice"

            published = None
            if item is not soup:
                node = item.select_one(date_selector) if date_selector else item
                hits = find_dates(node.get_text("\n", strip=True)) if node else []
                published = hits[0].value.isoformat() if hits else None
            notices.append(RawNotice(title=title, url=full_url, published=published))
    return notices


# ---------------------------------------------------------------------------
# Source kind: local (sample notices for demos, tests and evaluation)
# ---------------------------------------------------------------------------
_PLACEHOLDER = re.compile(r"\{\{([+-]\d+)(?::(\w+))?\}\}")


def render_placeholders(text: str, anchor: date) -> str:
    """Replace {{+7}} with a date 7 days after `anchor` (so demo dates never go stale)."""
    def repl(m: re.Match) -> str:
        day = anchor + timedelta(days=int(m.group(1)))
        if m.group(2) == "long":
            return f"{day.day} {day.strftime('%B %Y')}"
        if m.group(2) == "short":              # day and month only, no year (used to test the validator)
            return f"{day.day} {day.strftime('%B')}"
        return day.strftime("%d.%m.%Y")
    return _PLACEHOLDER.sub(repl, text)


def demo_anchor() -> date:
    """The day you first ran the demo. Saved so demo dates stay the same on every run."""
    path = Config.DATA_DIR / ".demo_anchor"
    try:
        return date.fromisoformat(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        today = date.today()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(today.isoformat(), encoding="utf-8")
        except OSError:
            pass
        return today


def parse_notice_file(raw_text: str) -> tuple[dict, str]:
    """Sample files look like:  Title: ...\\nDate: ...\\nURL: ...\\n---\\nbody text."""
    head, _, body = raw_text.partition("\n---")
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()
    return meta, body.lstrip("\n")


def fetch_local(cfg: dict, anchor: date | None = None) -> list[RawNotice]:
    folder = Config.BASE_DIR / cfg["path"]
    if not folder.is_dir():
        raise FetchError(f"Sample folder not found: {folder}")
    anchor = anchor or demo_anchor()
    notices = []
    for path in sorted(folder.glob("*.txt")):
        raw = render_placeholders(path.read_text(encoding="utf-8"), anchor)
        meta, body = parse_notice_file(raw)
        hits = find_dates(meta.get("date", ""))
        notices.append(RawNotice(
            title=meta.get("title", path.stem),
            url=meta.get("url") or f"local://{path.name}",
            published=hits[0].value.isoformat() if hits else None,
            text=body,
        ))
    return notices


def fetch_source(cfg: dict) -> list[RawNotice]:
    kind = cfg.get("kind")
    if kind == "local":
        return fetch_local(cfg)
    if kind == "html_list":
        return fetch_html_list(cfg)
    raise FetchError(f"Unknown source kind: {kind!r}")
