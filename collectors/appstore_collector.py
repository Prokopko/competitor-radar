"""
Apple App Store collector.

Uses the public iTunes Lookup API (no key required):
    https://itunes.apple.com/lookup?id=<app_id>&country=<cc>

Returns a "release version X" record only if the version is new
(deduped in the DB by uid, which includes version in the hash) + text from releaseNotes.
"""
import requests

import config
from collectors.base import normalize_item, to_iso


def collect(competitor, source):
    app_id = source["app_id"]
    country = source.get("country", "us")
    url = f"https://itunes.apple.com/lookup?id={app_id}&country={country}"

    resp = requests.get(url, headers=config.HTTP_HEADERS, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        return []

    app = data["results"][0]
    version = str(app.get("version", "")).strip()
    if not version:
        return []

    notes = (app.get("releaseNotes") or "").strip()
    app_name = app.get("trackName", competitor["name"])
    listing_url = app.get("trackViewUrl", "")
    released = to_iso(app.get("currentVersionReleaseDate"))

    title = f"{competitor['name']} iOS — version {version}"
    summary = notes or f"New version of {app_name} on the App Store ({country.upper()})."

    return [
        normalize_item(
            competitor, source,
            title=title, summary=summary, url=listing_url,
            version=version, published_at=released,
            extra={
                "store": "App Store",
                "country": country,
                "app_name": app_name,
                "rating": app.get("averageUserRating"),
            },
        )
    ]
