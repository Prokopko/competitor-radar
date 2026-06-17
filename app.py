"""
Competitor Radar — web server.

Run:
    uvicorn app:app --reload --port 8000
Open:
    http://localhost:8000

API endpoints:
    GET  /api/overview            — metrics + last run + list of competitors/markets
    GET  /api/campaign-tracker    — events from the last 7 days
    GET  /api/alerts              — app releases
    GET  /api/feed                — feed with filters (?q=&competitor=&type=&market=)
    GET  /api/digest               — weekly digest
    POST /api/refresh              — manual collection run (Refresh button)
    GET  /api/telegram-digest      — digest formatted for Telegram (used by n8n)
    POST /api/send-telegram-digest — sends the digest to TELEGRAM_CHAT_ID directly

Scheduler (timezone from SCHEDULER_TZ, default UTC):
    Mon 06:00 — collection run
    Mon 09:00 — send the weekly digest to Telegram (if TELEGRAM_BOT_TOKEN/CHAT_ID are set)

If N8N_REFRESH_WEBHOOK_URL is set, /api/refresh also POSTs its stats
(found/inserted/errors) to that URL — handy for an n8n "refresh -> Telegram" workflow.

For on-demand commands from Telegram (/start, /refresh, /digest, /status), run
telegram_bot.py alongside this app.
"""
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import ai_summary
import config
import database
import digest as analytics
import telegram_digest
from collectors import run_collection

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _HAS_SCHED = True
except Exception:
    _HAS_SCHED = False

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"
scheduler = None

# IANA timezone name for the weekly schedule below.
# Default Europe/Moscow — change SCHEDULER_TZ in .env if "Monday 09:00" should
# match a different local time.
SCHEDULER_TZ = os.environ.get("SCHEDULER_TZ", "Europe/Moscow")


def _send_digest_to_telegram(week: int = 0, refresh: bool = False) -> int:
    """Sends the weekly digest to TELEGRAM_CHAT_ID. Returns the number of messages sent."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not configured on the server.")

    if refresh:
        run_collection(progress=print)

    messages = telegram_digest.build_messages(week_index=week)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i, msg in enumerate(messages):
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=30)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram error: {data}")
        if i < len(messages) - 1:
            time.sleep(0.5)
    return len(messages)


def _weekly_telegram_job():
    try:
        sent = _send_digest_to_telegram(week=0, refresh=False)
        print(f"Weekly Telegram digest sent ({sent} message(s)).")
    except Exception as e:
        print(f"Weekly Telegram digest failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    global scheduler
    if _HAS_SCHED:
        scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
        # Monday 06:00 — collect fresh data.
        scheduler.add_job(
            lambda: run_collection(progress=print),
            CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=SCHEDULER_TZ),
            id="weekly_collection",
            replace_existing=True,
        )
        # Monday 09:00 — send the digest collected above to Telegram.
        scheduler.add_job(
            _weekly_telegram_job,
            CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=SCHEDULER_TZ),
            id="weekly_telegram_digest",
            replace_existing=True,
        )
        scheduler.start()
        print(f"Scheduler started ({SCHEDULER_TZ}): collection Mon 06:00, Telegram digest Mon 09:00")
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="Competitor Radar", lifespan=lifespan)


@app.get("/api/overview")
def overview():
    last = database.last_run()
    next_run = None
    if scheduler:
        job = scheduler.get_job("weekly_collection")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    return {
        "metrics": analytics.metrics(),
        "last_run": last,
        "next_run": next_run,
        "total_items": database.count_all(),
        "competitors": [
            {"id": c["id"], "name": c["name"], "market": c["market"]}
            for c in config.COMPETITORS
        ],
        "markets": sorted({c["market"] for c in config.COMPETITORS}),
        "activity_types": config.ACTIVITY_TYPES,
    }


@app.get("/api/campaign-tracker")
def campaign_tracker():
    return analytics.campaign_tracker()


@app.get("/api/alerts")
def alerts():
    return analytics.app_alerts()


@app.get("/api/feed")
def feed(
    q: str | None = Query(None),
    competitor: str | None = Query(None),
    type: str | None = Query(None),
    market: str | None = Query(None),
    limit: int = Query(300, le=2000),
):
    items = database.query_items(
        competitor_id=competitor, activity_type=type,
        market=market, search=q, limit=limit,
    )
    for i in items:
        i["activity_label"] = config.ACTIVITY_TYPES.get(i["activity_type"], i["activity_type"])
    return items


@app.get("/api/digest")
def digest():
    return analytics.weekly_digest()


@app.get("/api/digest-summary")
def digest_summary(week: int = Query(0, ge=0), refresh: bool = Query(False)):
    """
    AI-generated trends summary for one week of the digest (cached per week).
    ?refresh=true regenerates it even if a cached summary exists.
    """
    weeks = analytics.weekly_digest()
    if not weeks or week >= len(weeks):
        return {"week": None, "summary": "No competitor activity was recorded yet."}
    w = weeks[week]
    return {"week": w["week"], "summary": ai_summary.get_week_summary(w, force=refresh)}


@app.post("/api/refresh")
def refresh():
    stats = run_collection(progress=print)

    # Optional: notify an n8n workflow (e.g. to post the result to Telegram).
    webhook = os.environ.get("N8N_REFRESH_WEBHOOK_URL")
    if webhook:
        try:
            requests.post(webhook, json=stats, timeout=10)
        except requests.RequestException as e:
            print(f"n8n refresh webhook failed: {e}")

    return JSONResponse(stats)


@app.get("/api/telegram-digest")
def telegram_digest_endpoint(
    week: int = Query(0, ge=0),
    refresh: bool = Query(False),
):
    """
    Ready-to-send digest for Telegram (parse_mode=HTML).
    ?refresh=true — collect fresh data first.
    ?week=1 — previous week's digest.

    Convenient for n8n: one GET -> text -> Telegram sendMessage node.
    """
    if refresh:
        run_collection(progress=print)
    messages = telegram_digest.build_messages(week_index=week)
    return {
        "parse_mode": "HTML",
        "count": len(messages),
        "text": messages[0],       # usually the digest fits in one message
        "messages": messages,      # if long — split into several parts
    }


@app.post("/api/send-telegram-digest")
def send_telegram_digest(
    week: int = Query(0, ge=0),
    refresh: bool = Query(False),
):
    """
    Sends the weekly digest to the configured Telegram chat (the Telegram digest button).
    Requires the TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
    """
    try:
        sent = _send_digest_to_telegram(week=week, refresh=refresh)
    except RuntimeError as e:
        status = 400 if "not configured" in str(e) else 502
        raise HTTPException(status_code=status, detail=str(e))
    return {"sent": sent}


@app.get("/api/debug-env")
def debug_env():
    import datetime
    def mask(v): return v[:4] + "..." if v else "MISSING"
    return {
        "TELEGRAM_BOT_TOKEN": mask(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "TELEGRAM_CHAT_ID": mask(os.environ.get("TELEGRAM_CHAT_ID")),
        "OPENROUTER_API_KEY": mask(os.environ.get("OPENROUTER_API_KEY")),
        "RAILWAY_ENVIRONMENT": os.environ.get("RAILWAY_ENVIRONMENT", "MISSING"),
        "RAILWAY_PROJECT_ID": mask(os.environ.get("RAILWAY_PROJECT_ID")),
        "all_env_keys": sorted(os.environ.keys()),
        "server_time": datetime.datetime.utcnow().isoformat(),
    }


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# Serve static assets (in case assets are split out later).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
