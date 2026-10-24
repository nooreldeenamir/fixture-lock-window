# Fixture lock window

A small Python helper for prediction games that close entries a fixed number of minutes before kickoff. It returns a precise deadline and one of three states: **open**, **locked**, or **started**. A German text renderer and JSON output use the same calculation.

## Try it

Python 3.10+; standard library only. No installation, account, network request or API key.

```sh
python lock_window.py demo_fixtures.json --now 2026-10-24T17:49:59Z
python lock_window.py demo_fixtures.json --now 2026-10-24T17:50:00Z --json
python -m unittest -v
```

The included teams and fixtures are **invented demonstration data**, not live match information. An explicit `--now` makes the examples repeatable after the sample dates have passed. Without it, the CLI uses current UTC.

First fixture, one second before cutoff:

```text
Demo Heimteam A - Demo Gastteam B | Offen | Abgabe bis 2026-10-24T19:50:00+02:00 | UTC: 2026-10-24T17:50:00Z | 1s
```

At the cutoff itself, status becomes `locked` (`Gesperrt`). At kickoff, it becomes `started` (`Angepfiffen`). This resolves the otherwise easy-to-miss equality boundary.

## Input

```json
[{"home":"Example A","away":"Example B","kickoff_at":"2026-10-24T20:00:00+02:00"}]
```

`kickoff_at` must include seconds and an explicit UTC offset or `Z`. Date-only and timezone-free values fail instead of silently assuming a timezone. Offset hours/minutes are checked before Python parses them, since its parser can normalize an invalid offset such as `+02:99`. The RFC 3339 unknown-local-offset marker `-00:00` is rejected; use `Z`, `+00:00`, or a known nonzero offset. See [RFC 3339 section 4.3](https://www.rfc-editor.org/rfc/rfc3339#section-4.3). `--lock-minutes` defaults to 10; integer values from 0 to 1440 are accepted. Invalid input exits with code 2 and no partial success output.

## Integration boundary

```python
from datetime import datetime, timezone
from lock_window import describe_window

state = describe_window("2026-10-24T20:00:00+02:00", datetime.now(timezone.utc))
print(state["lock_utc"], state["status"])
```

This is a display/integration prototype, **not an authorization mechanism**. A production submission endpoint must obtain kickoff from trusted server data and enforce its deadline using the server clock. A client-supplied time or `--now` must never determine whether a real prediction is accepted.

Numeric offsets distinguish repeated daylight-saving hours, but the helper does not determine an offset from a stadium or a city. A production feed should supply UTC instants; a UI can then format them using the viewer's IANA timezone. Postponements, feed freshness, permission checks and prediction persistence are outside this small prototype.

The tests cover the exact cutoff, kickoff, midnight rollover, equivalent instants, half-hour offsets, repeated daylight-saving hours, invalid timestamps, malformed input and CLI replay.

## Assistance and ownership

Implementation, documentation and test execution used Codex AI coding assistance. This is a prototype with the limitations listed above.

Copyright (c) 2026 The Flywheel Corporation. All rights reserved. Public visibility does not grant a reuse license.
