"""
Competitor Radar — competitor and source configuration.

Each competitor is described by a set of sources. The source type determines
which collector processes it:

    rss        — RSS/Atom feed (company blog, news)
    news       — Google News search feed for the brand
    appstore   — Apple App Store app (by country + app_id)
    googleplay — Google Play app (by package id)
    webpage    — a regular page (change detection), e.g. a pricing page
    ads        — ad account / Ad Library (stub, needs a token)
    social     — social network (stub, needs an API/token)

IMPORTANT about sources that are NOT collected "out of the box":
  • ads / social are hidden behind platform auth and rate limits.
    Their collectors are extensible stubs. Plug in your own
    Facebook Ad Library token / session cookies etc. See collectors/.
"""

# Market is used for the "by market" filter.
COMPETITORS = [
    {
        "id": "monzo",
        "name": "Monzo",
        "market": "UK",
        "sources": [
            {"type": "rss", "name": "Monzo Blog", "url": "https://monzo.com/blog/feed.xml"},
            {"type": "news", "name": "Monzo News", "query": "Monzo bank"},
            {"type": "appstore", "name": "Monzo iOS", "country": "gb", "app_id": "1052238659"},
            {"type": "googleplay", "name": "Monzo Android", "package": "co.uk.getmondo"},
            {"type": "webpage", "name": "Monzo Pricing", "url": "https://monzo.com/pricing/"},
            {"type": "ads", "name": "Monzo Ads", "platform": "meta", "page": "Monzo"},
            {"type": "social", "name": "Monzo X", "platform": "x", "handle": "monzo"},
        ],
    },
    {
        "id": "n26",
        "name": "N26",
        "market": "EU",
        "sources": [
            {"type": "rss", "name": "N26 Blog", "url": "https://n26.com/en-eu/blog/feed"},
            {"type": "news", "name": "N26 News", "query": "N26 bank"},
            {"type": "appstore", "name": "N26 iOS", "country": "de", "app_id": "956857223"},
            {"type": "googleplay", "name": "N26 Android", "package": "de.number26.android"},
            {"type": "webpage", "name": "N26 Pricing", "url": "https://n26.com/en-eu/our-accounts"},
            {"type": "social", "name": "N26 X", "platform": "x", "handle": "n26"},
        ],
    },
    {
        "id": "nubank",
        "name": "Nubank",
        "market": "LATAM",
        "sources": [
            {"type": "news", "name": "Nubank News", "query": "Nubank Nu Holdings"},
            {"type": "appstore", "name": "Nubank iOS", "country": "br", "app_id": "814456780"},
            {"type": "googleplay", "name": "Nubank Android", "package": "com.nu.production"},
            {"type": "webpage", "name": "Nubank Site", "url": "https://nubank.com.br/"},
            {"type": "ads", "name": "Nubank Ads", "platform": "meta", "page": "nubank"},
        ],
    },
    {
        "id": "skyro",
        "name": "Skyro",
        "market": "PH",
        "sources": [
            {"type": "news", "name": "Skyro News", "query": "Skyro Philippines lending"},
            {"type": "googleplay", "name": "Skyro Android", "package": "ph.skyro.app"},
            {"type": "webpage", "name": "Skyro Site", "url": "https://www.skyro.ph/"},
        ],
    },
    {
        "id": "plata",
        "name": "Plata",
        "market": "MX",
        "sources": [
            {"type": "news", "name": "Plata News", "query": "Plata card Mexico fintech"},
            {"type": "appstore", "name": "Plata iOS", "country": "mx", "app_id": "6470689746"},
            {"type": "googleplay", "name": "Plata Android", "package": "mx.plata.app"},
            {"type": "webpage", "name": "Plata Pricing", "url": "https://www.platacard.mx/"},
        ],
    },
    {
        "id": "wise",
        "name": "Wise",
        "market": "Global",
        "sources": [
            {"type": "rss", "name": "Wise Blog", "url": "https://wise.com/gb/blog/rss.xml"},
            {"type": "news", "name": "Wise News", "query": "Wise transfer Wise plc"},
            {"type": "appstore", "name": "Wise iOS", "country": "gb", "app_id": "612261027"},
            {"type": "googleplay", "name": "Wise Android", "package": "com.transferwise.android"},
            {"type": "webpage", "name": "Wise Pricing", "url": "https://wise.com/gb/pricing/"},
        ],
    },
    {
        "id": "chime",
        "name": "Chime",
        "market": "US",
        "sources": [
            {"type": "news", "name": "Chime News", "query": "Chime banking app"},
            {"type": "appstore", "name": "Chime iOS", "country": "us", "app_id": "836215269"},
            {"type": "googleplay", "name": "Chime Android", "package": "com.onedebit.chime"},
            {"type": "webpage", "name": "Chime Site", "url": "https://www.chime.com/"},
        ],
    },
    {
        "id": "starling",
        "name": "Starling Bank",
        "market": "UK",
        "sources": [
            {"type": "rss", "name": "Starling Blog", "url": "https://www.starlingbank.com/blog/feed/"},
            {"type": "news", "name": "Starling News", "query": "Starling Bank"},
            {"type": "appstore", "name": "Starling iOS", "country": "gb", "app_id": "956806430"},
            {"type": "googleplay", "name": "Starling Android", "package": "com.starlingbank.android"},
            {"type": "webpage", "name": "Starling Pricing", "url": "https://www.starlingbank.com/accounts/"},
        ],
    },
]

# Activity types (for the filter and the UI color code).
ACTIVITY_TYPES = {
    "app_release": "App release",
    "pricing": "Pricing change",
    "blog": "Blog / content",
    "news": "News / PR",
    "ad": "Ad",
    "social": "Social",
    "website": "Website change",
}

# How many days count as "this week" in metrics and the Campaign Tracker.
WEEK_WINDOW_DAYS = 7

# User-Agent for network requests (some sites block the default one).
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CompetitorRadar/1.0; "
        "+https://example.com/competitor-radar)"
    )
}

# Network request timeout, seconds.
HTTP_TIMEOUT = 20


def competitor_by_id(cid: str):
    for c in COMPETITORS:
        if c["id"] == cid:
            return c
    return None
