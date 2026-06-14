"""
Base collector interface.

A collector receives (competitor, source) and returns a list of normalized
record dicts, ready to be written to the DB via database.insert_items().

Every collector is isolated: exceptions are caught by the registry, so one
failing source doesn't break the whole collection run.
"""
from datetime import datetime, timezone
import config
import classifier
from database import make_uid, now_iso


def normalize_item(competitor, source, *, title, summary="", url="",
                   version="", published_at=None, source_type=None, extra=None):
    """Builds a record in the unified format + assigns activity_type."""
    st = source_type or source["type"]
    activity = classifier.classify(title, summary, st)
    return {
        "uid": make_uid(competitor["id"], st, url, title, version),
        "competitor_id": competitor["id"],
        "competitor": competitor["name"],
        "market": competitor.get("market"),
        "source_type": st,
        "source_name": source.get("name"),
        "activity_type": activity,
        "title": title.strip()[:500],
        "summary": (summary or "").strip()[:2000],
        "url": url,
        "version": version,
        "published_at": published_at,
        "collected_at": now_iso(),
        "extra": extra or {},
    }


def to_iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt, tz=timezone.utc).isoformat()
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return None
