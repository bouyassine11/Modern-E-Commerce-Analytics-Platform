import logging
from pathlib import Path
from typing import Any, Optional

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

    def extract_all(
        self,
        monitor: Optional[Any] = None,
        run_id: Optional[int] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        raw = {}
        for table_name in self.file_map:
            logger.info("Extracting %s...", table_name)
            task_run_id = None
            if monitor and run_id:
                task_run_id = monitor.start_task(
                    task_name=f"extract_{table_name}",
                    task_type="extract",
                )
            try:
                rows = self.extract(table_name)
                raw[table_name] = rows
                if monitor and task_run_id:
                    monitor.complete_task(
                        task_run_id,
                        rows_processed=len(rows),
                    )
            except Exception as exc:
                if monitor and task_run_id:
                    monitor.fail_task(task_run_id, error_message=str(exc))
                raise
        return raw
