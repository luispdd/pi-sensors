"""Unit test for log_sync.py cursor parsing, file sequencing, and log record pagination."""

import os
import shutil
import tempfile
import unittest

from boards.pico_2w.services.log_sync import (
    get_log_files,
    parse_cursor,
    get_next_file,
    read_log_records,
) if False else None  # Dynamic import below to handle path differences


class TestLogSync(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, os.path.abspath("boards/pico-2w"))
        from services.log_sync import (
            get_log_files,
            parse_cursor,
            get_next_file,
            read_log_records,
        )
        self.get_log_files = get_log_files
        self.parse_cursor = parse_cursor
        self.get_next_file = get_next_file
        self.read_log_records = read_log_records

        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cursor_parsing(self):
        files = ["2026-09-22.csv", "2026-09-23.csv"]
        # Default when cursor is None
        self.assertEqual(self.parse_cursor(None, files), ("2026-09-22.csv", 0))
        self.assertEqual(self.parse_cursor("", files), ("2026-09-22.csv", 0))

        # Cursor with filename and line
        self.assertEqual(self.parse_cursor("2026-09-22:50", files), ("2026-09-22.csv", 50))
        self.assertEqual(self.parse_cursor("2026-09-22.csv:50", files), ("2026-09-22.csv", 50))

    def test_next_file(self):
        files = ["2026-09-21.csv", "2026-09-22.csv", "2026-09-23.csv"]
        self.assertEqual(self.get_next_file("2026-09-21.csv", files), "2026-09-22.csv")
        self.assertEqual(self.get_next_file("2026-09-22.csv", files), "2026-09-23.csv")
        self.assertIsNone(self.get_next_file("2026-09-23.csv", files))

    def test_read_log_records_single_file(self):
        csv_file = os.path.join(self.test_dir, "2026-09-22.csv")
        with open(csv_file, "w") as f:
            f.write("timestamp,device_id,temperature_c,humidity_pct\n")
            for i in range(100):
                f.write(f"2026-09-22T10:{i:02d}:00,pico-1w,{20.0 + i * 0.1:.1f},{50.0:.1f}\n")

        # First sync: size=50, no cursor
        res = self.read_log_records(self.test_dir, None, 50)
        self.assertEqual(len(res["data"]), 50)
        self.assertEqual(res["next_cursor"], "2026-09-22:50")
        self.assertEqual(res["data"][0]["ts"], "2026-09-22T10:00:00")
        self.assertEqual(res["data"][49]["ts"], "2026-09-22T10:49:00")

        # Second sync: size=50, cursor="2026-09-22:50"
        res2 = self.read_log_records(self.test_dir, "2026-09-22:50", 50)
        self.assertEqual(len(res2["data"]), 50)
        self.assertEqual(res2["next_cursor"], "2026-09-22:100")
        self.assertEqual(res2["data"][0]["ts"], "2026-09-22T10:50:00")
        self.assertEqual(res2["data"][49]["ts"], "2026-09-22T10:99:00")

        # Third sync: EOF of file
        res3 = self.read_log_records(self.test_dir, "2026-09-22:100", 50)
        self.assertEqual(len(res3["data"]), 0)
        self.assertEqual(res3["next_cursor"], "2026-09-22:100")

    def test_read_log_records_cross_boundary(self):
        f1 = os.path.join(self.test_dir, "2026-09-22.csv")
        with open(f1, "w") as f:
            f.write("timestamp,device_id,temperature_c,humidity_pct\n")
            for i in range(110):
                f.write(f"2026-09-22T{i:03d},pico-1w,21.0,50.0\n")

        f2 = os.path.join(self.test_dir, "2026-09-23.csv")
        with open(f2, "w") as f:
            f.write("timestamp,device_id,temperature_c,humidity_pct\n")
            for i in range(50):
                f.write(f"2026-09-23T{i:03d},pico-1w,22.0,51.0\n")

        # Query cursor=2026-09-22:100 with size=50 (10 remaining from day 22, 40 from day 23)
        res = self.read_log_records(self.test_dir, "2026-09-22:100", 50)
        self.assertEqual(len(res["data"]), 50)
        self.assertEqual(res["next_cursor"], "2026-09-23:40")
        self.assertEqual(res["data"][0]["ts"], "2026-09-22T100")
        self.assertEqual(res["data"][9]["ts"], "2026-09-22T109")
        self.assertEqual(res["data"][10]["ts"], "2026-09-23T000")
        self.assertEqual(res["data"][49]["ts"], "2026-09-23T039")


if __name__ == "__main__":
    unittest.main()
