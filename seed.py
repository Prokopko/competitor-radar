"""
Demo data so the dashboard can be viewed without a live collection run.

Run:
    python seed.py

This is NOT needed for production use — real data comes from run_collection().
Demo records are marked with extra.demo=true.
"""
import random
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone

import config
from database import init_db, insert_items, make_uid, now_iso

random.seed(7)


def _iso(days_ago, hours_ago=0):
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
    return dt.isoformat()


def _source_url(source):
    """Builds a real-looking URL for a source, same as the live collectors would."""
    stype = source["type"]
    if stype in ("rss", "webpage"):
        return source.get("url", "")
    if stype == "appstore":
        return f"https://apps.apple.com/{source.get('country', 'us')}/app/id{source['app_id']}"
    if stype == "googleplay":
        return f"https://play.google.com/store/apps/details?id={source['package']}"
    if stype == "news":
        return ("https://news.google.com/search?q=" + quote_plus(source["query"])
                + "&hl=en-US&gl=US&ceid=US:en")
    if stype == "ads":
        page = source.get("page", "")
        return ("https://www.facebook.com/ads/library/?active_status=active"
                "&ad_type=all&country=ALL&q=" + quote_plus(page))
    if stype == "social":
        handle = source.get("handle", "")
        if source.get("platform") == "x":
            return f"https://x.com/{handle}"
        return ""
    return ""


# Event templates: (competitor_id, source_type, activity_type, title, summary, version, days_ago)
EVENTS = [
    ("monzo", "rss", "blog", "Monzo launches joint accounts for families",
     "New blog post: a shared account for families with limits for kids.", "", 1),
    ("monzo", "appstore", "app_release", "Monzo iOS — version 6.31.0",
     "Fixes and improvements to push notifications.", "6.31.0", 2),
    ("monzo", "webpage", "pricing", "Monzo changed the pricing content: Monzo Pricing",
     "A change was detected on the pricing page.", "", 4),
    ("nubank", "googleplay", "app_release", "Nubank Android — version 8.5.0",
     "Home screen redesign, new investment products.", "8.5.0", 1),
    ("nubank", "news", "news", "Nubank reports growth in its customer base",
     "Quarterly results: growth in active customers in Mexico.", "", 3),
    ("plata", "webpage", "pricing", "Plata changed the pricing content: Plata Pricing",
     "Update to the card terms page.", "", 2),
    ("plata", "appstore", "app_release", "Plata iOS — version 2.14.1",
     "Faster virtual card issuance.", "2.14.1", 5),
    ("n26", "rss", "blog", "N26 adds shared savings Spaces",
     "Save together with a partner in a shared Space.", "", 4),
    ("wise", "news", "news", "Wise cuts transfer fees to Asia",
     "The company announced revised pricing for several corridors.", "", 5),
    ("wise", "appstore", "app_release", "Wise iOS — version 8.40.1",
     "Improved verification process.", "8.40.1", 7),
    ("chime", "news", "news", "Chime reportedly preparing to expand its product lineup",
     "Media reports point to new savings features.", "", 8),
    ("starling", "rss", "blog", "Starling updates business accounts",
     "New accounting tools for small businesses.", "", 9),
    ("skyro", "googleplay", "app_release", "Skyro Android — version 3.7.0",
     "Faster loan approval, new onboarding.", "3.7.0", 2),
    ("skyro", "webpage", "website", "Skyro changed the page content: Skyro Site",
     "Update to the home page.", "", 10),
    ("monzo", "news", "news", "Monzo raises a new funding round",
     "Reports indicate the company's valuation has increased.", "", 12),
    ("nubank", "ads", "ad", "Nubank launches anniversary promo",
     "A series of ad creatives across social media.", "", 11),
]


def seed():
    init_db()
    items = []
    for cid, stype, atype, title, summary, version, days_ago in EVENTS:
        comp = config.competitor_by_id(cid)
        if not comp:
            continue
        source = next((s for s in comp["sources"] if s["type"] == stype), {"type": stype, "name": stype})
        url = _source_url(source)
        items.append({
            "uid": make_uid(cid, stype, url, title, version),
            "competitor_id": cid,
            "competitor": comp["name"],
            "market": comp["market"],
            "source_type": stype,
            "source_name": source.get("name", stype),
            "activity_type": atype,
            "title": title,
            "summary": summary,
            "url": url,
            "version": version,
            "published_at": _iso(days_ago, random.randint(0, 20)),
            "collected_at": now_iso(),
            "extra": {"demo": True},
        })
    n = insert_items(items)
    print(f"Loaded demo records: {n} (out of {len(items)})")


if __name__ == "__main__":
    seed()
