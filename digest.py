"""
Analytics on top of the collected records:
  • metrics()         — summary for a window (total updates, most active competitor, breakdown by type)
  • campaign_tracker()— what happened in the last N days (flat list of events)
  • app_alerts()      — latest app releases (App Store / Google Play)
  • weekly_digest()   — grouped by ISO week and competitor
"""
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

import config
from database import query_items


def _parse(dt_str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_time(item):
    return _parse(item.get("published_at")) or _parse(item.get("collected_at"))


def metrics(days=config.WEEK_WINDOW_DAYS):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items = query_items(since=since, limit=5000)

    per_comp = Counter(i["competitor"] for i in items)
    per_type = Counter(i["activity_type"] for i in items)

    top_comp = per_comp.most_common(1)[0] if per_comp else (None, 0)

    return {
        "window_days": days,
        "total_updates": len(items),
        "active_competitors": len(per_comp),
        "top_competitor": {"name": top_comp[0], "count": top_comp[1]},
        "by_competitor": [{"name": k, "count": v} for k, v in per_comp.most_common()],
        "by_type": [
            {"type": k, "label": config.ACTIVITY_TYPES.get(k, k), "count": v}
            for k, v in per_type.most_common()
        ],
    }


def campaign_tracker(days=config.WEEK_WINDOW_DAYS, limit=50):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items = query_items(since=since, limit=limit)
    out = []
    for i in items:
        out.append({
            "competitor": i["competitor"],
            "competitor_id": i["competitor_id"],
            "activity_type": i["activity_type"],
            "activity_label": config.ACTIVITY_TYPES.get(i["activity_type"], i["activity_type"]),
            "title": i["title"],
            "url": i["url"],
            "version": i["version"],
            "when": i.get("published_at") or i.get("collected_at"),
        })
    return out


def app_alerts(days=30, limit=30):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items = query_items(activity_type="app_release", since=since, limit=limit)
    alerts = []
    for i in items:
        extra = i.get("extra") or "{}"
        alerts.append({
            "competitor": i["competitor"],
            "version": i["version"],
            "title": i["title"],
            "url": i["url"],
            "when": i.get("published_at") or i.get("collected_at"),
            "store": "App Store" if i["source_type"] == "appstore" else "Google Play",
        })
    return alerts


def weekly_digest(weeks=6):
    """Groups records by ISO week and competitor."""
    since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
    items = query_items(since=since, limit=5000)

    # week_key -> competitor -> [events]
    grouped = defaultdict(lambda: defaultdict(list))
    for i in items:
        t = _event_time(i)
        if not t:
            continue
        iso_year, iso_week, _ = t.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        grouped[week_key][i["competitor"]].append({
            "activity_type": i["activity_type"],
            "activity_label": config.ACTIVITY_TYPES.get(i["activity_type"], i["activity_type"]),
            "title": i["title"],
            "url": i["url"],
            "when": i.get("published_at") or i.get("collected_at"),
        })

    digest = []
    for week_key in sorted(grouped.keys(), reverse=True):
        comps = grouped[week_key]
        digest.append({
            "week": week_key,
            "total": sum(len(v) for v in comps.values()),
            "competitors": [
                {"competitor": c, "count": len(evs), "events": evs}
                for c, evs in sorted(comps.items(), key=lambda kv: -len(kv[1]))
            ],
        })
    return digest
