import csv
from pathlib import Path

from etl.extract import Extractor


class TestExtractor:
    def test_extract_returns_rows(self, fixtures_dir, sample_config):
        csv_path = fixtures_dir / "products.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["product_id", "name"])
            writer.writeheader()
            writer.writerow({"product_id": "1", "name": "Widget"})

        extractor = Extractor(sample_config)
        rows = extractor.extract("products")
        assert len(rows) == 1
        assert rows[0]["product_id"] == "1"

        csv_path.unlink()

    def test_extract_raises_on_missing_file(self, sample_config):
        extractor = Extractor(sample_config)
        import pytest
        with pytest.raises(FileNotFoundError):
            extractor.extract("products")

    def test_extract_raises_on_bad_table_name(self, sample_config):
        extractor = Extractor(sample_config)
        import pytest
        with pytest.raises(ValueError, match="No file mapping"):
            extractor.extract("nonexistent")

    def test_extract_all_returns_all_tables(self, fixtures_dir, sample_config):
        for name in ["products", "customers"]:
            path = fixtures_dir / f"{name}.csv"
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name"])
                writer.writeheader()
                writer.writerow({"id": "1", "name": "test"})

        extractor = Extractor(sample_config)
        result = extractor.extract_all()
        assert set(result.keys()) == {"products", "customers", "orders", "order_items", "payments"}
        assert len(result["products"]) == 1
        assert len(result["customers"]) == 1

        for name in ["products", "customers", "orders", "order_items", "payments"]:
            path = fixtures_dir / f"{name}.csv"
            if path.exists():
                path.unlink()
