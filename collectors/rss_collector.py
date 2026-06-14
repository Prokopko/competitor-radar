"""
RSS/Atom collector. Used for:
  • type=rss  — competitors' corporate blogs/news feeds
  • type=news — Google News feed for a search query (URL is built on the fly)
"""
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

import config
from collectors.base import normalize_item, to_iso


def _google_news_url(query: str) -> str:
    # Free Google News RSS feed for a search query.
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


def collect(competitor, source):
    if source["type"] == "news":
        feed_url = _google_news_url(source["query"])
    else:
        feed_url = source["url"]

    parsed = feedparser.parse(
        feed_url, request_headers=config.HTTP_HEADERS
    )

    items = []
    for entry in parsed.entries[:40]:
        title = entry.get("title", "").strip()
        if not title:
            continue
        link = entry.get("link", "")
        summary = entry.get("summary", "") or entry.get("description", "")

        published = None
        for key in ("published_parsed", "updated_parsed"):
            if entry.get(key):
                published = to_iso(
                    datetime.fromtimestamp(time.mktime(entry[key]), tz=timezone.utc)
                )
                break

        items.append(
            normalize_item(
                competitor, source,
                title=title, summary=summary, url=link, published_at=published,
            )
        )
    return items
