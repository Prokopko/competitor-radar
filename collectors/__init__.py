"""
Collector registry + orchestrator for a full collection run.

run_collection() iterates over all competitors and their sources, calls the
matching collector, stores the result in the DB, and writes the run log (runs).
Each source is isolated with try/except — one failure doesn't break the whole run.
"""
import importlib
import traceback

import config
from database import init_db, insert_items, start_run, finish_run

from collectors import (
    rss_collector,
    appstore_collector,
    googleplay_collector,
    webpage_collector,
    stub_collectors,
)

# type -> collect(competitor, source) function
REGISTRY = {
    "rss": rss_collector.collect,
    "news": rss_collector.collect,
    "appstore": appstore_collector.collect,
    "googleplay": googleplay_collector.collect,
    "webpage": webpage_collector.collect,
    "ads": stub_collectors.collect,
    "social": stub_collectors.collect,
}


def run_collection(progress=None):
    """
    Runs a full collection. progress — optional callback(msg:str).
    Returns a dict with statistics.
    """
    init_db()
    run_id = start_run()
    found = 0
    inserted = 0
    errors = []

    for comp in config.COMPETITORS:
        for source in comp["sources"]:
            stype = source["type"]
            collector = REGISTRY.get(stype)
            label = f"{comp['name']} / {source.get('name', stype)}"
            if not collector:
                errors.append(f"{label}: no collector for type {stype}")
                continue
            try:
                items = collector(comp, source) or []
                found += len(items)
                inserted += insert_items(items)
                if progress:
                    progress(f"✓ {label}: {len(items)} records")
            except Exception as e:  # isolate source failure
                msg = f"{label}: {type(e).__name__}: {e}"
                errors.append(msg)
                if progress:
                    progress(f"✗ {msg}")
                # Full traceback — stderr only, for debugging.
                traceback.print_exc()

    finish_run(run_id, found, inserted, errors)
    return {"run_id": run_id, "found": found, "inserted": inserted, "errors": errors}


if __name__ == "__main__":
    stats = run_collection(progress=print)
    print("\nTOTAL:", stats)
