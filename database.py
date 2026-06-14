"""
Competitor Radar SQLite storage.

Two tables:
  items   — all collected records (feed). Unique by uid (hash).
  runs    — collection run log (when, how many found).

Dedup: uid = sha1(competitor_id|source_type|url|title|version).
Re-collecting the same record doesn't create a duplicate — only INSERT OR IGNORE.
"""
import sqlite3
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "radar.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                uid           TEXT PRIMARY KEY,
                competitor_id TEXT NOT NULL,
                competitor    TEXT NOT NULL,
                market        TEXT,
                source_type   TEXT NOT NULL,
                source_name   TEXT,
                activity_type TEXT NOT NULL,
                title         TEXT NOT NULL,
                summary       TEXT,
                url           TEXT,
                version       TEXT,
                published_at  TEXT,           -- ISO8601, event date at the source
                collected_at  TEXT NOT NULL,  -- ISO8601, when we recorded this
                extra         TEXT            -- JSON with extra fields
            );
            CREATE INDEX IF NOT EXISTS idx_items_comp     ON items(competitor_id);
            CREATE INDEX IF NOT EXISTS idx_items_pub      ON items(published_at);
            CREATE INDEX IF NOT EXISTS idx_items_activity ON items(activity_type);
            CREATE INDEX IF NOT EXISTS idx_items_market   ON items(market);

            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at  TEXT NOT NULL,
                finished_at TEXT,
                found       INTEGER DEFAULT 0,
                inserted    INTEGER DEFAULT 0,
                errors      TEXT
            );

            -- Page content snapshot for change detection (webpage collector).
            CREATE TABLE IF NOT EXISTS page_snapshots (
                url         TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                seen_at     TEXT NOT NULL
            );

            -- Cached AI-generated digest summaries, one per ISO week.
            -- items_hash lets us regenerate the summary when that week's events change.
            CREATE TABLE IF NOT EXISTS ai_summaries (
                week_key    TEXT PRIMARY KEY,
                items_hash  TEXT NOT NULL,
                summary     TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );
            """
        )


def make_uid(competitor_id, source_type, url="", title="", version=""):
    raw = "|".join([competitor_id, source_type, url or "", title or "", version or ""])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def insert_items(items):
    """items: list of dicts. Returns the number of rows actually inserted (new)."""
    inserted = 0
    with _conn() as conn:
        for it in items:
            uid = it.get("uid") or make_uid(
                it["competitor_id"], it["source_type"],
                it.get("url", ""), it.get("title", ""), it.get("version", ""),
            )
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO items
                (uid, competitor_id, competitor, market, source_type, source_name,
                 activity_type, title, summary, url, version, published_at,
                 collected_at, extra)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    uid, it["competitor_id"], it["competitor"], it.get("market"),
                    it["source_type"], it.get("source_name"), it["activity_type"],
                    it["title"], it.get("summary"), it.get("url"),
                    it.get("version"), it.get("published_at"),
                    it.get("collected_at") or now_iso(),
                    json.dumps(it.get("extra", {}), ensure_ascii=False),
                ),
            )
            inserted += cur.rowcount
    return inserted


def start_run():
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (started_at) VALUES (?)", (now_iso(),)
        )
        return cur.lastrowid


def finish_run(run_id, found, inserted, errors=None):
    with _conn() as conn:
        conn.execute(
            "UPDATE runs SET finished_at=?, found=?, inserted=?, errors=? WHERE id=?",
            (now_iso(), found, inserted, json.dumps(errors or [], ensure_ascii=False), run_id),
        )


def last_run():
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_page_snapshot(url):
    with _conn() as conn:
        row = conn.execute(
            "SELECT fingerprint FROM page_snapshots WHERE url=?", (url,)
        ).fetchone()
        return row["fingerprint"] if row else None


def save_page_snapshot(url, fingerprint):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO page_snapshots (url, fingerprint, seen_at)
               VALUES (?,?,?)
               ON CONFLICT(url) DO UPDATE SET fingerprint=excluded.fingerprint,
                                              seen_at=excluded.seen_at""",
            (url, fingerprint, now_iso()),
        )


def query_items(competitor_id=None, activity_type=None, market=None,
                search=None, since=None, limit=500):
    sql = "SELECT * FROM items WHERE 1=1"
    args = []
    if competitor_id:
        sql += " AND competitor_id=?"; args.append(competitor_id)
    if activity_type:
        sql += " AND activity_type=?"; args.append(activity_type)
    if market:
        sql += " AND market=?"; args.append(market)
    if search:
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        args += [f"%{search}%", f"%{search}%"]
    if since:
        sql += " AND COALESCE(published_at, collected_at) >= ?"; args.append(since)
    sql += " ORDER BY COALESCE(published_at, collected_at) DESC LIMIT ?"
    args.append(limit)
    with _conn() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def count_all():
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]


def get_ai_summary(week_key, items_hash):
    """Returns the cached summary text, or None if missing/stale."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT summary FROM ai_summaries WHERE week_key=? AND items_hash=?",
            (week_key, items_hash),
        ).fetchone()
        return row["summary"] if row else None


def save_ai_summary(week_key, items_hash, summary):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO ai_summaries (week_key, items_hash, summary, generated_at)
               VALUES (?,?,?,?)
               ON CONFLICT(week_key) DO UPDATE SET items_hash=excluded.items_hash,
                                                    summary=excluded.summary,
                                                    generated_at=excluded.generated_at""",
            (week_key, items_hash, summary, now_iso()),
        )
