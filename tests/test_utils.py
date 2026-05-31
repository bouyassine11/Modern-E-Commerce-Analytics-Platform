import csv
from pathlib import Path

import pytest

from etl.utils import read_csv, write_csv


class TestReadCsv:
    def test_reads_csv_file(self, fixtures_dir):
        path = fixtures_dir / "test_read.csv"
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name"])
            writer.writerow(["1", "Alice"])
            writer.writerow(["2", "Bob"])

        rows = read_csv(path)
        assert len(rows) == 2
        assert rows[0]["id"] == "1"
        assert rows[0]["name"] == "Alice"

        path.unlink()

    def test_raises_on_missing_file(self, fixtures_dir):
        with pytest.raises(FileNotFoundError):
            read_csv(fixtures_dir / "nonexistent.csv")


class TestWriteCsv:
    def test_writes_csv_file(self, fixtures_dir):
        data = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        output_path = write_csv("test_write.csv", data, str(fixtures_dir))
        assert Path(output_path).exists()

        rows = read_csv(Path(output_path))
        assert len(rows) == 2
        assert rows[1]["name"] == "Bob"

        Path(output_path).unlink()

    def test_no_data_returns_empty(self, fixtures_dir):
        result = write_csv("empty.csv", [], str(fixtures_dir))
        assert result == ""
