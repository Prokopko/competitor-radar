"""
Collectors for ads and social media.

WHY STUBS AND NOT A FULL IMPLEMENTATION:
  Ad accounts and social platforms are hidden behind auth and rate limits:
    • Meta Ad Library — has an official API, but requires an access token
      (Graph API, /ads_archive). No token, no access.
    • X/Instagram/TikTok — heavily rate-limited, scraping violates ToS
      and gets banned easily; only works reliably via paid APIs/official
      partner access.

HOW TO ENABLE FOR REAL:
  1) Meta Ad Library: get a token, then call
     https://graph.facebook.com/v19.0/ads_archive
        ?search_terms=<brand>&ad_reached_countries=['GB']&access_token=<TOKEN>
     and map the response into normalize_item(...).
  2) Social: hook up the platform's official API (X API v2, etc.)
     or a third-party aggregator, and likewise return records via normalize_item.

For now the collectors return [] (nothing breaks), and the run log
honestly notes that the source isn't configured.
"""
import os

from collectors.base import normalize_item


def collect_ads(competitor, source):
    token = os.environ.get("META_ADS_TOKEN")
    if not token:
        # Not configured — silently skip (the registry will note it as skipped).
        return []

    # --- Example real integration (uncomment and finish) ---
    # import requests, config
    # params = {
    #     "search_terms": source.get("page", competitor["name"]),
    #     "ad_reached_countries": "['GB']",
    #     "ad_active_status": "ACTIVE",
    #     "fields": "ad_creative_bodies,ad_delivery_start_time,page_name",
    #     "access_token": token,
    # }
    # r = requests.get("https://graph.facebook.com/v19.0/ads_archive",
    #                  params=params, timeout=config.HTTP_TIMEOUT)
    # r.raise_for_status()
    # items = []
    # for ad in r.json().get("data", []):
    #     body = (ad.get("ad_creative_bodies") or [""])[0]
    #     items.append(normalize_item(
    #         competitor, source, source_type="ad",
    #         title=f"{competitor['name']} launched an ad campaign",
    #         summary=body,
    #         published_at=ad.get("ad_delivery_start_time"),
    #     ))
    # return items
    return []


def collect_social(competitor, source):
    # Same idea: requires the platform's official API.
    # Plug in a token and return records via normalize_item(source_type="social").
    return []


def collect(competitor, source):
    if source["type"] == "ads":
        return collect_ads(competitor, source)
    return collect_social(competitor, source)
