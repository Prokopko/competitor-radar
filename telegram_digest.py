"""
Formats the weekly digest into Telegram messages.

Telegram sendMessage:
  • parse_mode = HTML
  • 4096 character limit per message -> a long digest is split into parts.

build_messages() returns a list of ready-to-send HTML strings. Each string <= 4096.
Want to change the language of the labels? Everything is in the LABELS block below — a single dict.
"""
import html
import re

import ai_summary
import digest as analytics

# Emoji marker for the activity type (same color code as the dashboard).
TYPE_EMOJI = {
    "app_release": "🟣",
    "pricing": "🟡",
    "blog": "🔵",
    "news": "📰",
    "ad": "📣",
    "social": "🟢",
    "website": "🌐",
}

# Labels (change the language here only).
LABELS = {
    "header": "🛰 <b>Competitor Radar</b> — weekly digest {week}",
    "summary": "📊 Events: <b>{total}</b> · brands: <b>{brands}</b>",
    "leader": "🏆 Most active: <b>{name}</b> ({count})",
    "ai_summary": "🧠 <b>Trends this week</b>",
    "empty": "🛰 <b>Competitor Radar</b>\n\nNo competitor activity was recorded last week.",
    "more": "… and {n} more events",
}

MAX_LEN = 4096
# How many events to show per competitor, to avoid bloating the message.
MAX_EVENTS_PER_COMP = 6


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def _format_summary_line(line: str) -> str:
    """Escapes a summary line and converts **bold** markdown to <b>...</b>."""
    escaped = _esc(line)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def _event_line(ev) -> str:
    emoji = TYPE_EMOJI.get(ev["activity_type"], "•")
    title = _esc(ev["title"])
    if ev.get("url"):
        title = f'<a href="{_esc(ev["url"])}">{title}</a>'
    return f"{emoji} {title}"


def _build_week_text(week) -> str:
    lines = [LABELS["header"].format(week=week["week"])]
    brands = len(week["competitors"])
    lines.append(LABELS["summary"].format(total=week["total"], brands=brands))
    if week["competitors"]:
        top = week["competitors"][0]
        lines.append(LABELS["leader"].format(name=_esc(top["competitor"]), count=top["count"]))
    lines.append("")

    if week["competitors"]:
        summary = ai_summary.get_week_summary(week)
        if summary:
            lines.append(LABELS["ai_summary"])
            for s_line in summary.splitlines():
                s_line = s_line.strip()
                if s_line:
                    lines.append(_format_summary_line(s_line))
            lines.append("")

    for comp in week["competitors"]:
        lines.append(f"<b>{_esc(comp['competitor'])}</b> · {comp['count']}")
        shown = comp["events"][:MAX_EVENTS_PER_COMP]
        for ev in shown:
            lines.append(_event_line(ev))
        hidden = comp["count"] - len(shown)
        if hidden > 0:
            lines.append(LABELS["more"].format(n=hidden))
        lines.append("")

    return "\n".join(lines).strip()


def _split(text: str):
    """Splits long text into chunks <= MAX_LEN, breaking on line boundaries."""
    if len(text) <= MAX_LEN:
        return [text]
    parts, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > MAX_LEN:
            parts.append(buf.rstrip())
            buf = ""
        buf += line + "\n"
    if buf.strip():
        parts.append(buf.rstrip())
    return parts


def build_messages(week_index: int = 0):
    """
    Builds messages for the digest of the latest (default) week.
    week_index=0 — the most recent week, 1 — the previous one, etc.
    Returns a list of HTML strings to send sequentially.
    """
    weeks = analytics.weekly_digest()
    if not weeks or week_index >= len(weeks):
        return [LABELS["empty"]]
    return _split(_build_week_text(weeks[week_index]))


if __name__ == "__main__":
    for i, m in enumerate(build_messages()):
        print(f"--- message {i+1} ({len(m)} chars) ---")
        print(m)
