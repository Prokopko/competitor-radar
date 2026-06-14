"""
Activity type classifier.

The source already gives a "strong" hint (appstore -> app_release),
but for rss/news/webpage we refine it using keywords in the title/text:
pricing changes, ads, new features, etc.
"""
import re

# (regex, activity_type) — order matters: more specific patterns go first.
_RULES = [
    (r"\b(pricing|price|tariff|fee|fees|subscription|plan)\b", "pricing"),
    (r"\b(launch|introduc|new feature|now available|rolling out)\b", "blog"),
    (r"\b(campaign|advert|ad campaign|promo|sponsor)\b", "ad"),
    (r"\b(raises|funding|partnership|acquir|appoints|results|earnings)\b", "news"),
]


def classify(title: str, summary: str = "", source_type: str = "") -> str:
    # Hard mappings by source type.
    if source_type in ("appstore", "googleplay"):
        return "app_release"
    if source_type == "ads":
        return "ad"
    if source_type == "social":
        return "social"
    if source_type == "webpage":
        # webpage usually tracks a pricing page -> pricing, otherwise website
        text = f"{title} {summary}".lower()
        if re.search(r"\b(pricing|price|plan)\b", text):
            return "pricing"
        return "website"

    text = f"{title} {summary}".lower()
    for pattern, atype in _RULES:
        if re.search(pattern, text):
            return atype

    # rss defaults to blog, news defaults to news
    if source_type == "news":
        return "news"
    return "blog"
