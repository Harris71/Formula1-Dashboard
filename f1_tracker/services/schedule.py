from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from f1_tracker.config import JOLPICA_BASE_URL
from f1_tracker.services.http import cached_json

# Jolpica key -> short label, in weekend order.
_SESSION_KEYS = (
    ("FirstPractice", "Practice 1"),
    ("SecondPractice", "Practice 2"),
    ("ThirdPractice", "Practice 3"),
    ("SprintQualifying", "Sprint Qualifying"),
    ("SprintShootout", "Sprint Shootout"),
    ("Sprint", "Sprint"),
    ("Qualifying", "Qualifying"),
)

# Typical session lengths, used for calendar exports.
SESSION_DURATIONS = {
    "Race": timedelta(hours=2),
    "Sprint": timedelta(minutes=45),
    "Qualifying": timedelta(hours=1),
    "Sprint Qualifying": timedelta(minutes=45),
    "Sprint Shootout": timedelta(minutes=45),
}


@dataclass(frozen=True)
class Session:
    name: str
    start_utc: Optional[datetime]
    day: date

    def local(self) -> Optional[datetime]:
        return self.start_utc.astimezone() if self.start_utc else None


@dataclass(frozen=True)
class Race:
    round: int
    name: str
    official_name: str
    circuit: str
    locality: str
    country: str
    race_date: date
    race_time: Optional[str]
    status: str
    sessions: tuple[Session, ...] = field(default=())

    @property
    def label(self) -> str:
        return f"Round {self.round:02d} · {self.name}"

    @property
    def location(self) -> str:
        return f"{self.locality}, {self.country}"

    @property
    def is_sprint(self) -> bool:
        return any(s.name == "Sprint" for s in self.sessions)

    @property
    def start_utc(self) -> Optional[datetime]:
        return _combine_utc(self.race_date, self.race_time)

    def start_local(self) -> Optional[datetime]:
        start = self.start_utc
        return start.astimezone() if start else None

    def start_local_text(self) -> Optional[str]:
        """Race start in the viewer's local time zone, e.g. '14:00 CEST'."""
        local = self.start_local()
        if local is None:
            return None
        label = local.strftime("%H:%M %Z").strip()
        if local.date() != self.race_date:
            label = local.strftime("%a %d %b ") + label
        return label

    def weekend(self) -> tuple[Session, ...]:
        """All weekend sessions including the race, in order."""
        return self.sessions + (Session("Race", self.start_utc, self.race_date),)


def _combine_utc(day: date, raw_time: Optional[str]) -> Optional[datetime]:
    if not raw_time:
        return None
    try:
        start_time = datetime.strptime(raw_time, "%H:%M:%S").time()
    except (ValueError, TypeError):
        return None
    return datetime.combine(day, start_time, tzinfo=timezone.utc)


def _parse_date(day: str, raw_time: Optional[str]) -> tuple[date, Optional[str]]:
    parsed = datetime.strptime(day, "%Y-%m-%d").date()
    time_str = raw_time.strip().rstrip("Z") if raw_time else None
    return parsed, time_str


def _parse_sessions(race: dict[str, Any]) -> tuple[Session, ...]:
    sessions: list[Session] = []
    for key, label in _SESSION_KEYS:
        info = race.get(key)
        if not info or not info.get("date"):
            continue
        try:
            day, time_str = _parse_date(info["date"], info.get("time"))
        except ValueError:
            continue
        sessions.append(Session(label, _combine_utc(day, time_str), day))
    sessions.sort(key=lambda s: (s.day, s.start_utc or datetime.min.replace(tzinfo=timezone.utc)))
    return tuple(sessions)


def fetch_schedule(year: int) -> list[Race]:
    """Fetch the full race calendar for a season."""
    data = cached_json(f"{year}/races", f"{JOLPICA_BASE_URL}/{year}/races/?limit=100&format=json", year=year)
    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])

    result: list[Race] = []
    for race in races:
        circuit = race.get("Circuit", {}) or {}
        location = circuit.get("Location", {}) or {}
        race_date, race_time = _parse_date(race.get("date", ""), race.get("time"))
        result.append(
            Race(
                round=int(race.get("round", 0)),
                name=race.get("raceName", "Unknown GP"),
                official_name=race.get("officialName", race.get("raceName", "Unknown GP")),
                circuit=circuit.get("circuitName", "Unknown Circuit"),
                locality=location.get("locality", "-"),
                country=location.get("country", "-"),
                race_date=race_date,
                race_time=race_time,
                status=race.get("status", "Confirmed"),
                sessions=_parse_sessions(race),
            )
        )
    return result


def next_race(schedule: list[Race], today: Optional[date] = None) -> Optional[Race]:
    """First race on or after today."""
    today = today or date.today()
    upcoming = [race for race in schedule if race.race_date >= today]
    return upcoming[0] if upcoming else None


def previous_race(schedule: list[Race], today: Optional[date] = None) -> Optional[Race]:
    """Last race strictly before today."""
    today = today or date.today()
    past = [race for race in schedule if race.race_date < today]
    return past[-1] if past else None


def races_completed(schedule: list[Race], today: Optional[date] = None) -> int:
    today = today or date.today()
    return sum(1 for race in schedule if race.race_date < today)


def schedule_to_ics(year: int, schedule: list[Race]) -> str:
    """Season calendar as an iCalendar document (every timed session)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//F1 Tracker//Season Calendar//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:Formula 1 {year}",
    ]
    for race in schedule:
        for session in race.weekend():
            if session.start_utc is None:
                continue
            end = session.start_utc + SESSION_DURATIONS.get(session.name, timedelta(hours=1))
            uid = f"{year}-{race.round:02d}-{session.name.lower().replace(' ', '-')}@f1tracker"
            summary = f"{race.name} - {session.name}" if session.name != "Race" else race.name
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{session.start_utc:%Y%m%dT%H%M%SZ}",
                f"DTEND:{end:%Y%m%dT%H%M%SZ}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"LOCATION:{_ics_escape(race.circuit + ', ' + race.location)}",
                f"DESCRIPTION:{_ics_escape(f'Round {race.round} of the {year} season')}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")
