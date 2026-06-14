"""
Google Play collector.

Google Play has no official public API for versions, so we use the
google-play-scraper library (reads the public app page).

    pip install google-play-scraper

If the library isn't available, the collector doesn't crash — it raises,
which the registry catches and records as an error.
"""
import config
from collectors.base import normalize_item, to_iso

try:
    from google_play_scraper import app as gp_app
    _HAS_GP = True
except Exception:  # pragma: no cover
    _HAS_GP = False


def collect(competitor, source):
    if not _HAS_GP:
        raise RuntimeError(
            "google-play-scraper is not installed (pip install google-play-scraper)"
        )

    package = source["package"]
    info = gp_app(package, lang="en", country="us")

    version = str(info.get("version", "")).strip()
    if not version or version.lower() == "varies with device":
        # Some apps don't publish a version — use the update date instead.
        version = str(info.get("updated", ""))

    notes = (info.get("recentChanges") or "").strip()
    listing_url = info.get("url", f"https://play.google.com/store/apps/details?id={package}")
    released = to_iso(info.get("updated"))

    title = f"{competitor['name']} Android — version {version}"
    summary = notes or f"Update to {info.get('title', competitor['name'])} on Google Play."

    return [
        normalize_item(
            competitor, source,
            title=title, summary=summary, url=listing_url,
            version=version, published_at=released,
            extra={
                "store": "Google Play",
                "package": package,
                "score": info.get("score"),
            },
        )
    ]
