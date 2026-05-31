import logging
from pathlib import Path
from typing import Any

from etl.utils import read_csv

logger = logging.getLogger(__name__)


class Extractor:
    def __init__(self, config: dict):
        self.data_dir = Path(config["data"]["output_dir"])
        self.file_map = config["etl"]["file_map"]

    def extract(self, table_name: str) -> list[dict[str, Any]]:
        filename = self.file_map.get(table_name)
        if not filename:
            raise ValueError(f"No file mapping for table: {table_name}")

        filepath = self.data_dir / filename
        rows = read_csv(filepath)

        if not rows:
            logger.warning("Empty CSV: %s", filepath)

        return rows

    def extract_all(self) -> dict[str, list[dict[str, Any]]]:
        raw = {}
        for table_name in self.file_map:
            logger.info("Extracting %s...", table_name)
            raw[table_name] = self.extract(table_name)
        return raw
