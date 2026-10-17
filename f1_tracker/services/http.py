from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from f1_tracker.config import HTTP_CACHE_DIR, HTTP_USER_AGENT, LIVE_CACHE_TTL_SECONDS

# Jolpica's free tier is rate limited; keep a polite gap between requests.
_REQUEST_PACE_SECONDS = 0.35
_TIMEOUT = (10, 30)

_pace_lock = threading.Lock()
_last_request_at = 0.0
_session_lock = threading.Lock()
_session: Optional[requests.Session] = None


def _http() -> requests.Session:
    """Shared keep-alive session with retry/backoff for flaky connections."""
    global _session
    with _session_lock:
        if _session is None:
            retry = Retry(
                total=3,
                connect=3,
                read=2,
                backoff_factor=0.8,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",),
                respect_retry_after_header=True,
            )
            session = requests.Session()
            session.headers["User-Agent"] = HTTP_USER_AGENT
            session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
            _session = session
        return _session


def _pace() -> None:
    global _last_request_at
    with _pace_lock:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < _REQUEST_PACE_SECONDS:
            time.sleep(_REQUEST_PACE_SECONDS - elapsed)
        _last_request_at = time.monotonic()


def get_json(url: str) -> dict[str, Any]:
    _pace()
    response = _http().get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key.strip("/"))
    return HTTP_CACHE_DIR / f"{safe}.json"


def _read_cache(path: Path) -> Optional[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(path: Path, data: dict[str, Any], final: bool = False) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"saved_at": time.time(), "final": final, "data": data}), encoding="utf-8")
        temp.replace(path)
    except OSError:
        pass


def is_live_season(year: int) -> bool:
    from datetime import date

    return year >= date.today().year


def cached_json(
    key: str,
    url: str,
    year: Optional[int] = None,
    is_final: Optional[Callable[[dict[str, Any]], bool]] = None,
) -> dict[str, Any]:
    """Disk-cached GET. Live-season entries expire; stale copies are served offline.

    ``is_final`` marks a live-season payload as settled (e.g. a completed
    round's results) so it is kept forever like historical data.
    """
    path = _cache_path(key)
    entry = _read_cache(path)
    ttl = LIVE_CACHE_TTL_SECONDS if year is not None and is_live_season(year) else None
    if entry is not None:
        age = time.time() - float(entry.get("saved_at", 0))
        if ttl is None or entry.get("final") or age < ttl:
            return entry["data"]
    try:
        data = get_json(url)
    except requests.RequestException:
        if entry is not None:
            return entry["data"]
        raise
    _write_cache(path, data, final=bool(is_final and is_final(data)))
    return data
