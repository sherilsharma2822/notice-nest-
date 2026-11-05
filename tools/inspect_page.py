"""Help you fill in config/sources.yaml for a real university site.

    python tools/inspect_page.py https://your-university.example.edu/notices

It downloads the page (politely, obeying robots.txt) and prints the links that look like
notices, together with the HTML "path" of each link, so you can write CSS selectors.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup  # noqa: E402

from app.services.fetcher import polite_get  # noqa: E402


def describe(tag) -> str:
    name = tag.name
    if tag.get("id"):
        name += f"#{tag['id']}"
    if tag.get("class"):
        name += "." + ".".join(tag["class"])
    return name


def html_path(tag, depth: int = 5) -> str:
    parts, node = [], tag
    while node is not None and node.name not in (None, "[document]") and len(parts) < depth:
        parts.append(describe(node))
        node = node.parent
    return " > ".join(reversed(parts))


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python tools/inspect_page.py <page-url>")
        raise SystemExit(1)
    url = sys.argv[1]
    resp = polite_get(url)
    if resp is None:
        print("Could not download the page (blocked by robots.txt, offline, or an error).")
        raise SystemExit(1)

    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("a[href]")
    print(f"Page title: {soup.title.get_text(strip=True) if soup.title else '(none)'}")
    print(f"Total links: {len(links)}   Tables: {len(soup.select('table'))}   Lists: {len(soup.select('ul, ol'))}")
    if len(soup.get_text(strip=True)) < 300:
        print("WARNING: very little text. The page may build its content with JavaScript, "
              "which this tool cannot run. See docs/SOURCES_GUIDE.md.")

    candidates = [a for a in links if ".pdf" in a["href"].lower() or "notice" in a.get_text(" ").lower()
                  or "circular" in a.get_text(" ").lower()]
    print(f"\nLinks that look like notices: {len(candidates)}\n")
    for a in candidates[:12]:
        print(f"- text : {a.get_text(' ', strip=True)[:90]}")
        print(f"  href : {urljoin(url, a['href'])}")
        print(f"  path : {html_path(a)}\n")
    if candidates:
        print("Tip: look at the 'path' lines. If they all end in 'tr > td > a', try item_selector: \"table tr\".")
        print("If they end in 'li > a', try item_selector: \"ul li\". Then test with:")
        print('   python -m app.jobs.run_once --source "My University - Notices"')


if __name__ == "__main__":
    main()
