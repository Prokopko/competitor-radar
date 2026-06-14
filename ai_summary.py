"""
AI-generated "what happened this week" summary for the digest.

generate_summary(week) turns one week of `weekly_digest()` data into a short
list of bullet points describing what competitors actually did, cross-competitor
/ cross-market patterns, and a closing recommendation. Meant to make the raw
event list easier to scan at a glance.

Uses OpenRouter (model below, free tier) if OPENROUTER_API_KEY is set; otherwise
falls back to a simple rule-based summary so the feature still works without a key.

get_week_summary() caches the result per ISO week in the database and only
regenerates it when that week's events change (see database.get_ai_summary).
"""
import hashlib
import json
import os

import requests

import config
import database

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Free model on OpenRouter. Override with OPENROUTER_MODEL if it's retired/rate-limited
# (see https://openrouter.ai/models?max_price=0 for currently available free models).
DEFAULT_MODEL = "openai/gpt-oss-120b:free"

# Bump this when PROMPT_TEMPLATE or _fallback_summary changes shape, so cached
# summaries (keyed by items_hash) are regenerated instead of reused as-is.
PROMPT_VERSION = "v5"

PROMPT_TEMPLATE = """You are a market analyst writing the "Trends this week" section of a \
competitive intelligence digest for a product/marketing team at a fintech company.

Below is this week's tracked activity. Each competitor is tagged with its market, \
followed by its events as [activity type] title.

{events_block}

Write 3-4 short bullet points (each one sentence, starting with "- ") summarizing WHAT \
competitors actually did this week: specific launches, pricing or feature changes, \
campaigns, partnerships, app updates, etc. Focus on substance, not counts — never \
mention how many events/updates were recorded. Where relevant, group similar moves by \
different competitors or markets into a single bullet. Make the last bullet a concrete, \
actionable recommendation for what to watch next. Refer to specific competitors and \
markets by name. Do not invent facts beyond what's listed above. Output only the bullet \
points in plain text, nothing else — no markdown formatting (no **bold**, no headers)."""


def _competitor_market(name):
    for c in config.COMPETITORS:
        if c["name"] == name:
            return c.get("market")
    return None


def _items_hash(week) -> str:
    payload = {
        "version": PROMPT_VERSION,
        "competitors": [
            {
                "competitor": c["competitor"],
                "events": [(e["activity_type"], e["title"]) for e in c["events"]],
            }
            for c in week["competitors"]
        ],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _events_block(week, max_events_per_comp=12) -> str:
    lines = []
    for comp in week["competitors"]:
        market = _competitor_market(comp["competitor"])
        tag = f" [{market}]" if market else ""
        lines.append(f"{comp['competitor']}{tag} ({comp['count']} events):")
        for ev in comp["events"][:max_events_per_comp]:
            label = config.ACTIVITY_TYPES.get(ev["activity_type"], ev["activity_type"])
            lines.append(f"  - [{label}] {ev['title']}")
        hidden = comp["count"] - min(len(comp["events"]), max_events_per_comp)
        if hidden > 0:
            lines.append(f"  - … and {hidden} more")
    return "\n".join(lines)


def _fallback_summary(week) -> str:
    """Simple rule-based bullet list, used when no OPENROUTER_API_KEY is configured."""
    comps = week["competitors"]
    if not comps:
        return "- No competitor activity was recorded this week."

    def _highlight(comp):
        market = _competitor_market(comp["competitor"])
        market_str = f" ({market})" if market else ""
        ev = comp["events"][0]
        label = config.ACTIVITY_TYPES.get(ev["activity_type"], ev["activity_type"]).lower()
        return f"- {comp['competitor']}{market_str}: {label} — \"{ev['title']}\""

    lines = [_highlight(c) for c in comps[:3]]

    type_counts = {}
    for c in comps:
        for ev in c["events"]:
            label = config.ACTIVITY_TYPES.get(ev["activity_type"], ev["activity_type"])
            type_counts[label] = type_counts.get(label, 0) + 1
    top_types = sorted(type_counts.items(), key=lambda kv: -kv[1])[:2]
    if top_types:
        types_str = " and ".join(label.lower() for label, _ in top_types)
        lines.append(f"- Overall, this week's activity leaned towards {types_str}.")

    lines.append(
        f"- Worth watching: {comps[0]['competitor']}'s next steps and whether other "
        f"competitors follow with similar moves."
    )
    return "\n".join(lines)


def generate_summary(week) -> str:
    """Calls OpenRouter to summarize the week; falls back if no key/error."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key or not week["competitors"]:
        return _fallback_summary(week)

    prompt = PROMPT_TEMPLATE.format(events_block=_events_block(week))
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    try:
        r = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return text.strip() or _fallback_summary(week)
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return _fallback_summary(week)


def get_week_summary(week, force: bool = False) -> str:
    """Cached wrapper around generate_summary(), keyed by ISO week + event contents."""
    week_key = week["week"]
    items_hash = _items_hash(week)
    if not force:
        cached = database.get_ai_summary(week_key, items_hash)
        if cached is not None:
            return cached
    summary = generate_summary(week)
    database.save_ai_summary(week_key, items_hash, summary)
    return summary
