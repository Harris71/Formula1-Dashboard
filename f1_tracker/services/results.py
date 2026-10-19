from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from f1_tracker.config import JOLPICA_BASE_URL
from f1_tracker.services.http import cached_json
from f1_tracker.services.schedule import Race, fetch_schedule


@dataclass(frozen=True)
class RaceRow:
    position: int
    driver: str
    family_name: str
    team: str
    grid: int  # 0 = pit lane start
    time: str  # winner's race time, gap ("+15.499") or the lapped status
    status: str
    points: float


@dataclass(frozen=True)
class QualiRow:
    position: int
    driver: str
    team: str
    q1: str
    q2: str
    q3: str


@dataclass(frozen=True)
class RaceWeekend:
    year: int
    race: Race
    results: tuple[RaceRow, ...]
    qualifying: tuple[QualiRow, ...]
    sprint: tuple[RaceRow, ...] = ()  # only sprint weekends, once the sprint has been run


def _has_races(data: dict[str, Any]) -> bool:
    return bool(data.get("MRData", {}).get("RaceTable", {}).get("Races"))


def _races(year: int, round_number: int, endpoint: str) -> list[dict[str, Any]]:
    key = f"{year}/{round_number}/{endpoint}"
    data = cached_json(key, f"{JOLPICA_BASE_URL}/{key}/?limit=100&format=json", year=year, is_final=_has_races)
    return data.get("MRData", {}).get("RaceTable", {}).get("Races", [])


def _name(driver: dict[str, Any]) -> str:
    return f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip() or "Unknown"


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _race_rows(year: int, round_number: int, endpoint: str, field: str) -> list[RaceRow]:
    """Classification rows of a Grand Prix ("results") or its sprint ("sprint")."""
    rows: list[RaceRow] = []
    for race_data in _races(year, round_number, endpoint)[:1]:
        for index, res in enumerate(race_data.get(field, []), start=1):
            driver = res.get("Driver", {})
            status = res.get("status", "")
            timing = (res.get("Time") or {}).get("time", "")
            if not timing and status.startswith("+"):
                timing = status  # e.g. "+1 Lap"
            rows.append(
                RaceRow(
                    position=_int(res.get("position"), index),
                    driver=_name(driver),
                    family_name=driver.get("familyName", "") or _name(driver),
                    team=(res.get("Constructor") or {}).get("name", "-"),
                    grid=_int(res.get("grid")),
                    time=timing,
                    status=status,
                    points=float(res.get("points", 0) or 0),
                )
            )
    return rows


def find_race(year: int, grand_prix: str) -> Race:
    """Resolve a Grand Prix name (exact, then partial match) to its calendar entry."""
    schedule = fetch_schedule(year)
    wanted = grand_prix.strip().lower()
    for race in schedule:
        if race.name.lower() == wanted:
            return race
    for race in schedule:
        haystack = f"{race.name} {race.circuit} {race.locality} {race.country}".lower()
        if wanted and wanted in haystack:
            return race
    raise ValueError(f"No {year} round matches “{grand_prix}”.")


def fetch_race_weekend(year: int, grand_prix: str) -> RaceWeekend:
    """Race, qualifying and (on sprint weekends) sprint classification for one round (Jolpica / Ergast)."""
    race = find_race(year, grand_prix)

    results = _race_rows(year, race.round, "results", "Results")
    sprint: list[RaceRow] = []
    if race.is_sprint:
        try:
            sprint = _race_rows(year, race.round, "sprint", "SprintResults")
        except requests.RequestException:
            pass  # the sprint is optional: its failure must not blank the Grand Prix results

    qualifying: list[QualiRow] = []
    for race_data in _races(year, race.round, "qualifying")[:1]:
        for index, res in enumerate(race_data.get("QualifyingResults", []), start=1):
            qualifying.append(
                QualiRow(
                    position=_int(res.get("position"), index),
                    driver=_name(res.get("Driver", {})),
                    team=(res.get("Constructor") or {}).get("name", "-"),
                    q1=res.get("Q1", "") or "-",
                    q2=res.get("Q2", "") or "-",
                    q3=res.get("Q3", "") or "-",
                )
            )

    return RaceWeekend(
        year=year, race=race, results=tuple(results), qualifying=tuple(qualifying), sprint=tuple(sprint)
    )


def weekend_span(race: Race) -> str:
    """'11 Apr – 13 Apr 2025' style weekend span for display."""
    days = [s.day for s in race.sessions] + [race.race_date]
    start = min(days)
    return f"{start:%d %b} – {race.race_date:%d %b %Y}" if start != race.race_date else f"{race.race_date:%d %b %Y}"
