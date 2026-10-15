"""Fetching and parsing ikman.lk pages.

Every ikman page embeds its data as JSON in `window.initialData = {...}`,
so we parse that instead of the HTML markup.
"""
import json
import re
import time
from datetime import datetime, timezone

import requests

BASE_URL = "https://ikman.lk"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_INITIAL_DATA = re.compile(r"window\.initialData\s*=\s*(\{.*?\})\s*</script>", re.S)


class ScrapeError(Exception):
    """The page did not have the structure we expect (site layout probably changed)."""


def _get(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(5 * attempt)


def _initial_data(html):
    match = _INITIAL_DATA.search(html)
    if not match:
        raise ScrapeError("window.initialData not found - ikman page layout may have changed")
    return json.loads(match.group(1))


def fetch_listing(search_url, page):
    """Return the regular ads on one search results page (paid 'topAds' are ignored)."""
    separator = "&" if "?" in search_url else "?"
    data = _initial_data(_get(f"{search_url}{separator}page={page}"))
    try:
        return data["serp"]["ads"]["data"]["ads"]
    except (KeyError, TypeError) as exc:
        raise ScrapeError("serp.ads.data.ads missing from listing page") from exc


def fetch_detail(slug):
    """Return the full ad (description, adDate, money, location, ...)."""
    data = _initial_data(_get(ad_url(slug)))
    try:
        return data["adDetail"]["data"]["ad"]
    except (KeyError, TypeError) as exc:
        raise ScrapeError(f"adDetail missing from ad page {slug}") from exc


def ad_url(slug):
    return f"{BASE_URL}/en/ad/{slug}"


def created_at(ad_id):
    """Ad IDs are Mongo ObjectIds: the first 8 hex chars are the creation Unix time."""
    return datetime.fromtimestamp(int(ad_id[:8], 16), timezone.utc)


def parse_price(text):
    """'Rs 35,000 /month' -> 35000. Returns None when there is no number."""
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None
