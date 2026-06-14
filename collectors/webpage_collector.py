"""
Webpage change-detection collector.

Downloads the page, extracts the visible text, and computes a "fingerprint".
If the fingerprint differs from the previous snapshot, it generates a change record.
Ideal for pricing pages: catches when a competitor tweaks prices/plans.

The first visit to a new page records the baseline and does NOT create a record
(otherwise everything would look "changed" on the first run).
"""
import hashlib
import re

import requests
from bs4 import BeautifulSoup

import config
from collectors.base import normalize_item
from database import get_page_snapshot, save_page_snapshot


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fingerprint(text: str) -> str:
    # Hash the whole (normalized) text — changes on any content edit.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect(competitor, source):
    url = source["url"]
    resp = requests.get(url, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()

    text = _visible_text(resp.text)
    fp = _fingerprint(text)

    previous = get_page_snapshot(url)
    save_page_snapshot(url, fp)

    if previous is None:
        # Baseline — first snapshot, no record created.
        return []
    if previous == fp:
        # No changes.
        return []

    # Content has changed.
    is_pricing = bool(re.search(r"(pricing|price|plan)", url.lower()
                                + " " + source.get("name", "").lower()))
    label = "pricing" if is_pricing else "page"
    title = f"{competitor['name']} changed the {label} content: {source.get('name')}"
    summary = (
        f"A change was detected on {url}. "
        f"Compare the current version with the previous check."
    )

    return [
        normalize_item(
            competitor, source,
            title=title, summary=summary, url=url,
            extra={"fingerprint": fp[:12]},
        )
    ]
