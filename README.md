# Competitor Radar

Autopilot competitor tracking for fintech. One dashboard instead of 70 tabs.

Tracks 8 competitors (Monzo, N26, Nubank, Skyro, Plata, Wise, Chime, Starling)
and collects their activity from public sources: blogs, news, App Store / Google Play
(app versions), pricing pages (change detection). Ads and social media are extensible
stub collectors (see below).

## What's inside

```
competitor_radar/
├── app.py                 FastAPI: API + dashboard serving + scheduler
├── config.py              competitors and their sources (edit here)
├── database.py            SQLite storage + dedup
├── classifier.py          activity type detection from text
├── digest.py              metrics, Campaign Tracker, alerts, weekly digest
├── seed.py                demo data (python seed.py)
├── telegram_bot.py        Telegram bot: /start, /refresh, /digest, /status
├── send_telegram.py       standalone: send the digest to Telegram once
├── get_chat_id.py         helper: find your Telegram chat_id
├── n8n_workflow.json      n8n: weekly digest → Telegram
├── n8n_workflow_refresh.json  n8n: refresh result → Telegram
├── n8n_workflow_telegram_bot.json  n8n: Telegram bot (/refresh, /digest, /status, /help)
├── collectors/            collectors by source type
│   ├── __init__.py        registry + run_collection() orchestrator
│   ├── rss_collector.py   blogs + news (Google News RSS)
│   ├── appstore_collector.py    iOS versions (iTunes Lookup API)
│   ├── googleplay_collector.py  Android versions (google-play-scraper)
│   ├── webpage_collector.py     page change detection (pricing)
│   └── stub_collectors.py       ads/social (token-gated stubs)
└── static/index.html      dashboard (Overview, Tracker, Alerts, Feed, Digest, ⌘K)
```

## Getting started

```bash
pip install -r requirements.txt
cp .env.example .env                 # fill in TELEGRAM_*/OPENROUTER_* to enable
                                      # Telegram digest + AI summary (optional)
python seed.py                       # optional: demo data for a first look
uvicorn app:app --reload --port 8000
# open http://localhost:8000
```

The **Refresh** button in the UI triggers a real collection run across all sources.

The built-in scheduler (in `app.py`) runs two jobs every week, in the timezone
set by `SCHEDULER_TZ` (default `Europe/Moscow`):

- **Monday 06:00** — collects fresh data from all sources.
- **Monday 09:00** — sends that week's digest to `TELEGRAM_CHAT_ID` via the bot
  (only if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are set).

Change the schedule in `app.py` (the two `CronTrigger(...)` calls in `lifespan()`).

## Dashboard

- **Overview** — metrics for the last 7 days, activity by competitor, breakdown by type.
- **Campaign Tracker** — what happened in the last 7 days, as a feed.
- **Alerts** — new App Store / Google Play releases.
- **Feed** — everything collected; filters by brand / type / market + search.
- **Digest** — events grouped by ISO week and competitor, with an AI "Trends this week"
  summary on top (see below).
- **⌘K** — command palette, quick search across all records.

Each activity type has its own color (app release, pricing, blog, news,
ads, social, website) — events are classified instantly by color.

## Adding/changing a competitor

Edit `COMPETITORS` in `config.py`. For each source, set `type`:
`rss`, `news`, `appstore`, `googleplay`, `webpage`, `ads`, `social`.

## Ads and social media

These sources are hidden behind platform auth and rate limits, so they
ship as extensible stubs in `collectors/stub_collectors.py`:

- **Meta Ad Library** — an official API exists, but requires an access token.
  The file has a ready-to-use commented-out example request to
  `graph.facebook.com/.../ads_archive`.
  Put the token in the `META_ADS_TOKEN` environment variable.
- **Social (X/Instagram/TikTok)** — hook up the platform's official API and
  return records via `normalize_item(..., source_type="social")`.

Until tokens are set, these sources are simply skipped and don't break collection.

## How it works

1. `run_collection()` walks all competitors and sources, calling the right collector.
2. Each source is isolated with `try/except` — one failure doesn't break the whole run;
   errors are written to the `runs` log.
3. Records are normalized and stored in SQLite with dedup by `uid`
   (`sha1` of brand+type+url+title+version) — re-collecting doesn't create duplicates.
4. The `webpage` collector keeps a "fingerprint" of the page text and creates an event
   only if the content changed (the first visit is a baseline, with no event).
5. The dashboard reads aggregates via the JSON API.

## AI trends summary

Each week's digest opens with a short bullet list (3-4 points) describing what
competitors actually *did* this week (launches, pricing/feature changes, campaigns,
partnerships — not just counts), grouping similar moves across competitors/markets,
with a closing bullet recommending what to watch next. It's shown in the dashboard's
**Digest** tab and at the top of the Telegram digest.

- Powered by [OpenRouter](https://openrouter.ai/) if `OPENROUTER_API_KEY` is set in `.env`
  (default model: `openai/gpt-oss-120b:free`, a free model — override with
  `OPENROUTER_MODEL` if it's retired or rate-limited).
- Without a key, a simple rule-based summary is used instead (same spot, less nuance).
- Generated once per ISO week and cached in `radar.db` (`ai_summaries` table); it's
  regenerated automatically when that week's events change (e.g. after a refresh).
- `GET /api/digest-summary?week=N&refresh=true` to fetch/force-regenerate it directly.

## Telegram digest & bot

1. Create a bot via **@BotFather** (`/newbot`) and get a token.
2. Send the bot `/start`, then find your chat_id:
   ```bash
   export TELEGRAM_BOT_TOKEN="7712345678:AAH...xyz"
   python get_chat_id.py
   ```
3. Put both values in `.env` (see `.env.example`-style block below) — they're
   loaded automatically by `app.py` and `telegram_bot.py` via `python-dotenv`.

```
TELEGRAM_BOT_TOKEN=7712345678:AAH...xyz
TELEGRAM_CHAT_ID=123456789
SCHEDULER_TZ=Europe/Moscow
RADAR_API_URL=http://localhost:8000
```

In the dashboard's **Digest** tab, the **Send to Telegram** button calls
`POST /api/send-telegram-digest` and delivers the current digest to
`TELEGRAM_CHAT_ID` right away. The same digest is also served by
`GET /api/telegram-digest` (parse_mode=HTML, `?refresh=true`, `?week=N`) —
a convenient entry point for n8n or `send_telegram.py`.

### On-demand bot commands

Two interchangeable ways to handle `/refresh`, `/digest`, `/status`, `/help` —
**pick one** (a Telegram bot can only receive updates one way at a time: either
long polling or a webhook, not both).

**Option A — n8n (`n8n_workflow_telegram_bot.json`)**, recommended if you're
already running n8n. See [Automation with n8n](#automation-with-n8n) below.

**Option B — `telegram_bot.py`**, a small Python long-poller, no n8n needed:

```bash
python telegram_bot.py
# or persistently:
nohup python telegram_bot.py > /tmp/telegram_bot.log 2>&1 &
```

Commands (restricted to `TELEGRAM_CHAT_ID` if it's set):

- **/start**, **/help** — explains what the bot does and lists the tracked competitors.
- **/refresh** — runs a full collection now (`POST /api/refresh`) and reports how many
  new items were found.
- **/digest** — sends this week's digest immediately.
- **/status** — last run, next scheduled run, and total items tracked.

The weekly digest itself is still sent automatically by the scheduler in `app.py`
(Monday 09:00, `SCHEDULER_TZ`) — the bot is only for on-demand commands.

## Automation with n8n

### Telegram bot (`n8n_workflow_telegram_bot.json`)

A full n8n-native replacement for `telegram_bot.py` — `/start`, `/help`, `/refresh`,
`/digest`, `/status`, and the same reply-keyboard buttons, all built from n8n nodes
calling this app's API:

```
Telegram Trigger (message) → Allowed chat? (IF, restricts to TELEGRAM_CHAT_ID)
                            → Normalize command (Code: maps button labels → commands)
                            → Route command (Switch)
   /start, /help → Send help (with reply-keyboard buttons)
   /refresh      → Send "running…" → POST /api/refresh → Format result → Send result
   /digest       → GET /api/telegram-digest → Split digest parts → Send each part
   /status       → GET /api/overview → Format status → Send status
   (anything else) → Send "Unknown command"
```

Setup:
1. Import `n8n_workflow_telegram_bot.json` (Workflows → Import from File).
2. In every Telegram node, attach a credential with your bot token.
3. In the three HTTP Request nodes, the URL must be reachable from n8n:
   - **n8n self-hosted in Docker, app on the same host** —
     `http://host.docker.internal:8000`.
   - **n8n Cloud, app running locally** — expose it with a tunnel, e.g.
     [ngrok](https://ngrok.com): `ngrok http 8000` gives a public
     `https://xxxx.ngrok-free.dev` URL (changes on every restart unless you
     have a paid static domain — update the 3 HTTP nodes when it changes).
     Free ngrok shows an interstitial page to browsers, so the nodes also send
     an `ngrok-skip-browser-warning: true` header.
   - **App deployed publicly** (VPS, Render, Railway, …) — use that URL directly.
4. The "Allowed chat?" node restricts the bot to one chat ID — n8n Cloud blocks
   `$env` access in expressions, so it's hardcoded in the IF node's condition.
   Replace `388790734` with your own `TELEGRAM_CHAT_ID` (or relax/remove the
   condition to allow anyone who messages the bot).
5. **Activate** the workflow — n8n registers a Telegram webhook automatically.
6. Set the "/" command menu once (Telegram webhook and long polling are
   mutually exclusive, so do this instead of `telegram_bot.py`'s `setMyCommands`):
   ```bash
   curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setMyCommands" \
     -H "Content-Type: application/json" \
     -d '{"commands":[{"command":"start","description":"What this bot does"},{"command":"refresh","description":"Run data collection now"},{"command":"digest","description":"Send this week'"'"'s digest"},{"command":"status","description":"Last run / next run / items tracked"},{"command":"help","description":"Show help and buttons"}]}'
   ```

> **Stop `telegram_bot.py`** before activating this workflow — once n8n sets a
> webhook for the bot, Telegram stops delivering updates via `getUpdates`
> (long polling), so the two can't run at the same time.

### Weekly digest (`n8n_workflow.json`)

Import `n8n_workflow.json` (Workflows → Import from File). The chain:

```
Weekly trigger (Mon 06:00) → HTTP GET /api/telegram-digest?refresh=true
                          → Split digest parts → Telegram sendMessage
```

Before running:
- In the HTTP node, replace `localhost:8000` with an address reachable from n8n
  (if n8n runs in Docker and the radar runs on the host — `http://host.docker.internal:8000`).
- In the Telegram node, attach a credential with the bot token and set the chat_id
  (the template reads it from the n8n environment variable `TELEGRAM_CHAT_ID`).

> **Don't run this alongside the built-in scheduler** unless you disable one of
> them — both `n8n_workflow.json` and `app.py`'s Monday 09:00 job will send the
> weekly digest, resulting in a duplicate message.

### Refresh notification (`n8n_workflow_refresh.json`)

Import `n8n_workflow_refresh.json`. It exposes a Webhook that, when called, posts
the refresh result (`found` / `inserted` / `errors`) to Telegram:

```
Webhook (POST /webhook/competitor-radar-refresh) → Telegram sendMessage
```

To wire it up: in the Telegram node, attach your bot credential, then set
`N8N_REFRESH_WEBHOOK_URL` in `.env` to the webhook's URL. From then on, every
**Refresh** (button, scheduler, or `/refresh` in Telegram) also POSTs its stats
to n8n, which forwards a summary to Telegram.

## Notes

- Some competitor feeds/pages may change their URL or block bots —
  check the `url` in `config.py` if a source stops returning data.
- `radar.db` (SQLite) is created automatically in the project root.
