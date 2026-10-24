"""Deterministic prediction deadlines. No network calls or prediction submission."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")


def parse_timestamp(value: str) -> datetime:
    """Require an explicit numeric UTC offset; never infer the user's zone."""
    if not isinstance(value, str) or not RFC3339.fullmatch(value):
        raise ValueError("Use a timestamp with seconds and an explicit offset, e.g. 2026-10-24T18:00:00Z")
    if value.endswith("-00:00"):
        raise ValueError("Unknown local offset -00:00 is not a trusted kickoff timezone; use Z or a known offset")
    if not value.endswith("Z") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError("Offset hours/minutes are out of range")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid timestamp: {value}") from error
    if result.utcoffset() is None:
        raise ValueError("A UTC offset is required")
    return result


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def describe_window(kickoff_at: str, now: datetime, lock_minutes: int = 10) -> dict:
    """Open strictly before cutoff; equality is already locked."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be an aware datetime")
    if type(lock_minutes) is not int or not 0 <= lock_minutes <= 1440:
        raise ValueError("lock_minutes must be an integer from 0 to 1440")
    kickoff = parse_timestamp(kickoff_at)
    lock_at = kickoff - timedelta(minutes=lock_minutes)
    current = now.astimezone(timezone.utc)
    if current >= kickoff:
        state, label = "started", "Angepfiffen"
    elif current >= lock_at:
        state, label = "locked", "Gesperrt"
    else:
        state, label = "open", "Offen"
    return {
        "status": state,
        "status_de": label,
        "kickoff_utc": utc_text(kickoff),
        "lock_utc": utc_text(lock_at),
        "kickoff_with_source_offset": kickoff.isoformat(),
        "lock_with_source_offset": lock_at.isoformat(),
        "seconds_until_lock": max(0, math.ceil((lock_at - current).total_seconds())),
        "lock_minutes": lock_minutes,
    }


def render_fixtures(fixtures: object, now: datetime, lock_minutes: int) -> list[dict]:
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("Expected a nonempty JSON array of fixtures")
    results = []
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            raise ValueError(f"Fixture {index}: expected an object")
        for key in ("home", "away", "kickoff_at"):
            if not isinstance(fixture.get(key), str) or not fixture[key].strip():
                raise ValueError(f"Fixture {index}: {key} must be a nonempty string")
        try:
            window = describe_window(fixture["kickoff_at"], now, lock_minutes)
        except ValueError as error:
            raise ValueError(f"Fixture {index}: {error}") from error
        results.append({"home": fixture["home"], "away": fixture["away"], **window})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path, help="JSON array; kickoff_at requires a UTC offset")
    parser.add_argument("--now", help="Explicit reference time for replay/tests; defaults to current UTC")
    parser.add_argument("--lock-minutes", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Machine-readable result")
    args = parser.parse_args(argv)
    try:
        now = parse_timestamp(args.now) if args.now else datetime.now(timezone.utc)
        fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
        result = render_fixtures(fixtures, now, args.lock_minutes)
    except (ValueError, OSError) as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"as_of_utc": utc_text(now), "fixtures": result}, ensure_ascii=False, indent=2))
    else:
        print(f"Stand: {utc_text(now)} | All deadlines include an explicit UTC offset")
        for row in result:
            print(f"{row['home']} - {row['away']} | {row['status_de']} | "
                  f"Abgabe bis {row['lock_with_source_offset']} | "
                  f"UTC: {row['lock_utc']} | {row['seconds_until_lock']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
