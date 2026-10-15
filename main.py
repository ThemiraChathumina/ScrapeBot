"""One run of the bot: find new matching ads and email them.

"New" means not seen by an earlier run. Seen ad IDs are kept in the state file,
which the GitHub workflow commits back to the repo after each run. Tracking IDs
(instead of comparing post times with the last run time) avoids missing ads
that were created before a run but only approved/published after it.

Usage:
  python main.py                      normal run
  python main.py --dry-run            print matches, send nothing, save nothing
  python main.py --dry-run --ignore-seen --lookback-hours 72   test on recent ads
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import filters
import notifier
import scraper

ROOT = Path(__file__).parent
SRI_LANKA = timezone(timedelta(hours=5, minutes=30))
log = logging.getLogger("scrapeBot")


def load_state(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path, seen, retention_days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept = {ad_id: ts for ad_id, ts in seen.items() if datetime.fromisoformat(ts) >= cutoff}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"seen": kept}, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def collect_candidates(config, seen, cutoff):
    """Unseen ads created after cutoff, from as many pages as needed (up to max_pages)."""
    candidates = {}
    for page in range(1, config["max_pages"] + 1):
        ads = scraper.fetch_listing(config["search_url"], page)
        if page == 1 and not ads:
            raise scraper.ScrapeError("0 ads on page 1 - search URL or site layout may have changed")
        for ad in ads:
            if ad["id"] not in seen and scraper.created_at(ad["id"]) >= cutoff:
                candidates[ad["id"]] = ad
        # Results are newest first, so stop once the page reaches ads older than cutoff.
        if not ads or scraper.created_at(ads[-1]["id"]) < cutoff:
            break
        time.sleep(config["request_delay_seconds"])
    return list(candidates.values())


def evaluate(ad, config):
    """Return (match_dict, None) or (None, reason). Raises on network errors."""
    keywords = config["exclude_keywords"]
    allowed = config.get("allow_phrases") or []
    price_cfg = config["price"]

    price = scraper.parse_price(ad.get("price"))
    if not filters.price_ok(price, price_cfg["min"], price_cfg["max"]):
        return None, f"price {ad.get('price')!r}"
    hit = filters.excluded_keyword(ad.get("title"), keywords, allowed)
    if hit:
        return None, f"title contains {hit!r}"

    time.sleep(config["request_delay_seconds"])
    detail = scraper.fetch_detail(ad["slug"])
    amount = (detail.get("money") or {}).get("amount") or ad.get("price")
    if not filters.price_ok(scraper.parse_price(amount), price_cfg["min"], price_cfg["max"]):
        return None, f"detail price {amount!r}"
    description = detail.get("description") or ""
    hit = filters.excluded_keyword(f"{detail.get('title', '')}\n{description}", keywords, allowed)
    if hit:
        return None, f"description contains {hit!r}"

    posted = detail.get("adDate")
    posted = datetime.fromisoformat(posted) if posted else scraper.created_at(ad["id"])
    snippet = description if len(description) <= 400 else description[:400].rstrip() + "..."
    return {
        "title": detail.get("title") or ad["title"],
        "price": amount,
        "location": (detail.get("location") or {}).get("name") or ad.get("location", ""),
        "posted": posted.astimezone(SRI_LANKA).strftime("%d %b %Y %I:%M %p"),
        "url": scraper.ad_url(ad["slug"]),
        "snippet": snippet,
    }, None


def run(args):
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    state_path = ROOT / config["state_file"]
    state = load_state(state_path)
    first_run = state is None and not args.dry_run
    seen = {} if (state is None or args.ignore_seen) else state["seen"]

    now = datetime.now(timezone.utc)
    lookback = args.lookback_hours or config["lookback_hours"]
    candidates = collect_candidates(config, seen, now - timedelta(hours=lookback))
    log.info("%d unseen ad(s) from the last %dh", len(candidates), lookback)

    if first_run:
        # No previous run, so nothing counts as "posted since the last run" yet.
        for ad in candidates:
            seen[ad["id"]] = now.isoformat()
        save_state(state_path, seen, config["seen_retention_days"])
        log.info("First run: recorded %d existing ad(s) without emailing", len(candidates))
        return

    matches, match_ids = [], []
    for ad in candidates:
        try:
            match, reason = evaluate(ad, config)
        except Exception:
            # Leave it unseen so the next run retries it.
            log.exception("Could not check ad %s (%s); will retry next run", ad["id"], ad.get("title"))
            continue
        if match:
            log.info("MATCH  %s | %s | %s", match["price"], match["title"], match["url"])
            matches.append(match)
            match_ids.append(ad["id"])
        else:
            log.info("skip   %s | %s", reason, ad.get("title"))
            seen[ad["id"]] = now.isoformat()

    if args.dry_run:
        log.info("Dry run: %d match(es); no email sent, state not saved", len(matches))
        return

    try:
        if matches:
            notifier.send_matches(matches)
            log.info("Emailed %d match(es)", len(matches))
            # Only mark matches as seen once the email went out, so a failed send is retried.
            for ad_id in match_ids:
                seen[ad_id] = now.isoformat()
    finally:
        save_state(state_path, seen, config["seen_retention_days"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print matches; no email, no state changes")
    parser.add_argument("--ignore-seen", action="store_true", help="treat every ad as unseen")
    parser.add_argument("--lookback-hours", type=int, help="override lookback_hours from config.yaml")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    run(args)


if __name__ == "__main__":
    main()
