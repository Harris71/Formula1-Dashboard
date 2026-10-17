from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

import requests

from f1_tracker.config import JOLPICA_BASE_URL
from f1_tracker.services.http import cached_json


@dataclass(frozen=True)
class DriverStanding:
    position: int
    driver: str
    nationality: str
    team: str
    points: str
    wins: str
    driver_id: str = ""
    number: str = ""
    code: str = ""


@dataclass(frozen=True)
class ConstructorStanding:
    position: int
    constructor: str
    points: str
    wins: str


def _cached_get_json(key: str, url: str) -> dict[str, Any]:
    parts = key.split("/")
    year = int(parts[0]) if parts[0].isdigit() else None
    # "{year}/{round}/..." payloads are settled once the round has data.
    per_round = len(parts) > 2 and parts[1].isdigit()
    return cached_json(key, url, year=year, is_final=_has_payload if per_round else None)


def _has_payload(data: dict[str, Any]) -> bool:
    mr = data.get("MRData", {})
    return bool(
        mr.get("RaceTable", {}).get("Races")
        or mr.get("StandingsTable", {}).get("StandingsLists")
    )


def _position(item: dict[str, Any], index: int) -> int:
    """Classified position; entrants Jolpica leaves unclassified ("-", no
    position, e.g. zero-point drivers in 2000) keep their place in its list,
    which already ranks them last, instead of 0 sorting them above the leader."""
    try:
        return int(item["position"])
    except (KeyError, TypeError, ValueError):
        return index


def _standings_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    return data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])


def fetch_driver_standings(year: int, round_number: Optional[int] = None) -> list[DriverStanding]:
    """Drivers' standings for a year — or as of a single round when given."""
    key = f"{year}/driverstandings" if not round_number else f"{year}/{round_number}/driverstandings"
    data = _cached_get_json(key, f"{JOLPICA_BASE_URL}/{key}/?format=json")
    lists = _standings_list(data)
    if not lists:
        return []

    standings: list[DriverStanding] = []
    for index, item in enumerate(lists[0].get("DriverStandings", []), start=1):
        driver = item.get("Driver", {})
        constructor = (item.get("Constructors") or [{}])[0]
        standings.append(
            DriverStanding(
                position=_position(item, index),
                driver=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                nationality=driver.get("nationality", "-"),
                team=constructor.get("name", "-"),
                points=item.get("points", "0"),
                wins=item.get("wins", "0"),
                driver_id=driver.get("driverId", ""),
                number=driver.get("permanentNumber", "") or "-",
                code=driver.get("code", "") or driver.get("familyName", "")[:3].upper(),
            )
        )
    return standings


def fetch_constructor_standings(year: int, round_number: Optional[int] = None) -> list[ConstructorStanding]:
    """Constructors' standings for a year — or as of a single round when given."""
    key = f"{year}/constructorstandings" if not round_number else f"{year}/{round_number}/constructorstandings"
    data = _cached_get_json(key, f"{JOLPICA_BASE_URL}/{key}/?format=json")
    lists = _standings_list(data)
    if not lists:
        return []

    standings: list[ConstructorStanding] = []
    for index, item in enumerate(lists[0].get("ConstructorStandings", []), start=1):
        constructor = item.get("Constructor", {})
        standings.append(
            ConstructorStanding(
                position=_position(item, index),
                constructor=constructor.get("name", "-"),
                points=item.get("points", "0"),
                wins=item.get("wins", "0"),
            )
        )
    return standings


def _session_result_rows(year: int, round_number: int, endpoint: str, field: str) -> list[dict[str, Any]]:
    key = f"{year}/{round_number}/{endpoint}"
    data = _cached_get_json(key, f"{JOLPICA_BASE_URL}/{key}/?limit=100&format=json")
    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return []

    results: list[dict[str, Any]] = []
    for res in races[0].get(field, []):
        driver = res.get("Driver", {})
        constructor = (res.get("Constructors") or [{}])[0]
        results.append({
            "driver_id": driver.get("driverId", ""),
            "number": driver.get("permanentNumber", "") or "-",
            "position_text": res.get("positionText", res.get("position", "")),
            "points": float(res.get("points", 0) or 0),
            "constructor": constructor.get("name", "-"),
        })
    return results


def fetch_race_results(year: int, round_number: int) -> list[dict[str, Any]]:
    """Grand Prix result rows for one race: identity, finishing text and points."""
    return _session_result_rows(year, round_number, "results", "Results")


def fetch_sprint_results(year: int, round_number: int) -> list[dict[str, Any]]:
    """Sprint result rows for one round (sprints only exist from 2021 on)."""
    try:
        return _session_result_rows(year, round_number, "sprint", "SprintResults")
    except requests.RequestException:
        return []


def fetch_progression_table(
    year: int,
    rounds: Sequence[int],
    which: str,
    progress: Optional[Callable[[int, int], None]] = None,
) -> list[dict[str, Any]]:
    """Final classification enriched with per-round results for every entrant.

    Returns one row per classified driver or constructor in final order; each
    row carries a per-round cell with points scored that round ('points',
    including sprints), cumulative points ('total') and best Grand Prix
    finish ('position').
    """
    final = fetch_constructor_standings(year) if which == "constructors" else fetch_driver_standings(year)

    def entry_for(rows: dict[str, dict], res: dict[str, Any]) -> dict:
        entry_id = res["constructor"] if which == "constructors" else res["driver_id"]
        return rows.setdefault(entry_id, {"positions": [], "points": 0.0})

    per_round: dict[int, dict[str, dict]] = {}
    total = len(rounds)
    for index, round_number in enumerate(rounds):
        rows: dict[str, dict] = {}
        for res in fetch_race_results(year, round_number):
            entry = entry_for(rows, res)
            entry["points"] += float(res["points"])
            position_text = str(res["position_text"])
            if position_text.isdigit():
                entry["positions"].append(int(position_text))
        for res in fetch_sprint_results(year, round_number):
            entry = entry_for(rows, res)
            entry["points"] += float(res["points"])
        per_round[round_number] = rows
        if progress:
            progress(index + 1, total)

    table_rows: list[dict] = []
    for standing in final:
        entry_id = standing.constructor if which == "constructors" else standing.driver_id
        cells: dict[int, Optional[dict]] = {}
        cumulative = 0.0
        for round_number in rounds:
            entry = per_round.get(round_number, {}).get(entry_id)
            if entry is None:
                cells[round_number] = None
                continue
            cumulative += entry["points"]
            cells[round_number] = {
                "points": entry["points"],
                "total": cumulative,
                "position": min(entry["positions"]) if entry["positions"] else None,
            }
        table_rows.append({
            "position": standing.position,
            "name": standing.constructor if which == "constructors" else standing.driver,
            "number": "-" if which == "constructors" else standing.number,
            "team": standing.team if which == "drivers" else "-",
            "points": standing.points,
            "cells": cells,
        })
    return table_rows


@dataclass(frozen=True)
class RaceResult:
    position: str
    driver: str
    code: str
    team: str
    time: str
    points: str
    grid: str


@dataclass(frozen=True)
class LastRace:
    round: int
    name: str
    circuit: str
    date: str
    results: tuple[RaceResult, ...]


def fetch_last_race(year: int) -> Optional[LastRace]:
    """Classification of the most recent Grand Prix in a season (None if none yet)."""
    key = f"{year}/last/results"
    data = _cached_get_json(key, f"{JOLPICA_BASE_URL}/{key}/?limit=100&format=json")
    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return None
    race = races[0]
    results = []
    for res in race.get("Results", []):
        driver = res.get("Driver", {})
        constructor = res.get("Constructor", {})
        timing = (res.get("Time") or {}).get("time") or res.get("status", "")
        results.append(
            RaceResult(
                position=res.get("positionText", res.get("position", "-")),
                driver=f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip(),
                code=driver.get("code", "") or driver.get("familyName", "")[:3].upper(),
                team=constructor.get("name", "-"),
                time=timing,
                points=res.get("points", "0"),
                grid=res.get("grid", "-"),
            )
        )
    return LastRace(
        round=int(race.get("round", 0)),
        name=race.get("raceName", "Grand Prix"),
        circuit=(race.get("Circuit") or {}).get("circuitName", "-"),
        date=race.get("date", ""),
        results=tuple(results),
    )


def get_wdc_summary(year: int) -> str:
    standings = fetch_driver_standings(year)
    if not standings:
        return f"No World Drivers' Championship data found for {year}."
    champion = standings[0]
    return f"The {year} World Drivers' Champion: {champion.driver}"


def get_wcc_summary(year: int) -> str:
    standings = fetch_constructor_standings(year)
    if not standings:
        return f"No World Constructors' Championship data found for {year}."
    champion = standings[0]
    return f"The {year} World Constructors' Champion: {champion.constructor}"
