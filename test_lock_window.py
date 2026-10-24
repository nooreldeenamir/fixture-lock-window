import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from lock_window import describe_window, main, parse_timestamp, render_fixtures


class WindowTests(unittest.TestCase):
    kickoff = "2026-10-24T20:00:00+02:00"

    def at(self, now, **kwargs):
        return describe_window(self.kickoff, parse_timestamp(now), **kwargs)

    def test_one_second_before_cutoff_is_open(self):
        result = self.at("2026-10-24T17:49:59Z")
        self.assertEqual((result["status"], result["seconds_until_lock"]), ("open", 1))

    def test_exact_cutoff_is_locked(self):
        result = self.at("2026-10-24T17:50:00Z")
        self.assertEqual((result["status"], result["seconds_until_lock"]), ("locked", 0))

    def test_kickoff_is_started(self):
        self.assertEqual(self.at("2026-10-24T18:00:00Z")["status"], "started")

    def test_past_game_has_no_negative_countdown(self):
        self.assertEqual(self.at("2026-10-25T18:00:00Z")["seconds_until_lock"], 0)

    def test_equal_instants_with_different_offsets(self):
        self.assertEqual(self.at("2026-10-24T19:50:00+02:00"), self.at("2026-10-24T17:50:00Z"))

    def test_half_hour_offset(self):
        result = describe_window("2026-10-24T23:30:00+05:30", parse_timestamp("2026-10-24T17:50:00Z"))
        self.assertEqual(result["lock_utc"], "2026-10-24T17:50:00Z")

    def test_midnight_rollover(self):
        result = describe_window("2026-10-25T00:05:00Z", parse_timestamp("2026-10-24T23:00:00Z"))
        self.assertEqual(result["lock_utc"], "2026-10-24T23:55:00Z")

    def test_dst_repeated_hour_needs_explicit_offset(self):
        now = parse_timestamp("2026-10-25T00:00:00Z")
        summer = describe_window("2026-10-25T02:30:00+02:00", now)
        winter = describe_window("2026-10-25T02:30:00+01:00", now)
        self.assertEqual(summer["lock_utc"], "2026-10-25T00:20:00Z")
        self.assertEqual(winter["lock_utc"], "2026-10-25T01:20:00Z")

    def test_rejects_ambiguous_or_invalid_timestamps(self):
        for value in ("2026-10-24", "2026-10-24T20:00:00", "2026-02-30T20:00:00Z", "2026-10-24T20:00:00+25:00", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timestamp(value)

    def test_rejects_naive_reference_clock(self):
        with self.assertRaises(ValueError):
            describe_window(self.kickoff, datetime(2026, 10, 24))

    def test_rejects_out_of_range_offset_minutes(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-10-24T20:00:00+02:99")

    def test_rejects_rfc3339_unknown_local_offset(self):
        with self.assertRaises(ValueError):
            parse_timestamp("2026-10-24T20:00:00-00:00")

    def test_rejects_bad_lock_intervals(self):
        for value in (-1, 1441, True, 2.5, "10"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.at("2026-10-24T17:00:00Z", lock_minutes=value)

    def test_rejects_partial_input_without_partial_success(self):
        fixtures = [{"home": "A", "away": "B", "kickoff_at": self.kickoff}, {"home": "C"}]
        with self.assertRaisesRegex(ValueError, "Fixture 1: away"):
            render_fixtures(fixtures, datetime.now(timezone.utc), 10)

    def test_cli_json_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fixtures.json"
            source.write_text(json.dumps([{"home": "A", "away": "B", "kickoff_at": self.kickoff}]), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([str(source), "--now", "2026-10-24T17:50:00Z", "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["fixtures"][0]["status"], "locked")

    def test_bad_file_returns_nonzero_and_no_success_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "bad.json"
            source.write_text("{bad json", encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main([str(source)])
            self.assertEqual(code, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("Invalid input", err.getvalue())


if __name__ == "__main__":
    unittest.main()
