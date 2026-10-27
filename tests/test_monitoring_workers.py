"""Offline smoke checks for bundled worker output and cache isolation."""

import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


WORKERS = Path(__file__).resolve().parents[1] / "VibeHUD/Resources"


class MonitoringWorkerTests(unittest.TestCase):
    def test_codex_quota_from_synthetic_rollout(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            sessions = home / ".codex/sessions"
            sessions.mkdir(parents=True)
            timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
            event = {
                "timestamp": timestamp,
                "payload": {
                    "type": "token_count",
                    "rate_limits": {
                        "plan_type": "plus",
                        "primary": {"window_minutes": 300, "used_percent": 85, "resets_at": 4102444800},
                        "secondary": {"window_minutes": 10080, "used_percent": 30, "resets_at": 4102444800},
                    },
                },
            }
            (sessions / "rollout-sample.jsonl").write_text(json.dumps(event) + "\n")
            cache = home / "private/codex.json"
            result = subprocess.run(
                [sys.executable, "-I", str(WORKERS / "codex_usage.py"), "--write", "--cache", str(cache),
                 "--sessions-dir", str(sessions), "--archived-dir", str(home / "archived")],
                capture_output=True, text=True, check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["windows"]["five_hour"]["used_percentage"], 85)
            self.assertEqual(payload["windows"]["seven_day"]["used_percentage"], 30)
            self.assertEqual(json.loads(cache.read_text()), payload)
            self.assertEqual(cache.stat().st_mode & 0o777, 0o600)

    def test_claude_statusline_from_synthetic_input(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "claude.json"
            result = subprocess.run(
                [sys.executable, "-I", str(WORKERS / "claude_statusline.py"), "--cache", str(cache)],
                input=json.dumps({"model": {"display_name": "Sample"}, "rate_limits": {
                    "five_hour": {"used_percentage": 22, "resets_at": None},
                    "seven_day": {"used_percentage": 61, "resets_at": None},
                }}), capture_output=True, text=True, check=True,
            )
            self.assertIn("5h 22%", result.stdout)
            self.assertIn("7d 61%", result.stdout)
            self.assertEqual(json.loads(cache.read_text())["windows"]["seven_day"]["used_percentage"], 61)
            self.assertEqual(cache.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
