import io
import logging
import csv
from typing import Any

import psycopg2

from etl.utils import get_connection

logger = logging.getLogger(__name__)


class Loader:
    def __init__(self, config: dict):
        self.db_config = config["database"]
        self.schema = config["database"]["schema"]
        self._table_map = {
            "products": "products_raw",
            "customers": "customers_raw",
            "orders": "orders_raw",
            "order_items": "order_items_raw",
            "payments": "payments_raw",
        }

    # ------------------------------------------------------------------
    # Schema bootstrapping
    # ------------------------------------------------------------------

    def ensure_schema(self, conn: psycopg2.extensions.connection) -> None:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
        logger.info("Schema '%s' ensured", self.schema)

    def truncate_table(self, conn: psycopg2.extensions.connection, raw_table: str) -> None:
        full_name = f"{self.schema}.{raw_table}"
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {full_name} RESTART IDENTITY CASCADE")
        logger.info("Truncated %s", full_name)

    # ------------------------------------------------------------------
    # Bulk load via COPY
    # ------------------------------------------------------------------

    def bulk_insert(
        self,
        conn: psycopg2.extensions.connection,
        raw_table: str,
        data: list[dict[str, Any]],
    ) -> int:
        if not data:
            logger.warning("No rows to load into %s", raw_table)
            return 0

        columns = list(data[0].keys())

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)
        buf.seek(0)

        full_name = f"{self.schema}.{raw_table}"

        with conn.cursor() as cur:
            cur.copy_expert(
                f"COPY {full_name} ({','.join(columns)}) FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER ',')",
                buf,
            )

        logger.info("Copied %d rows into %s", len(data), full_name)
        return len(data)

    # ------------------------------------------------------------------
    # Full load orchestration
    # ------------------------------------------------------------------

    def load_all(self, conn: psycopg2.extensions.connection, data: dict[str, list[dict]]) -> dict[str, int]:
        logger.info("=" * 50)
        logger.info("Load phase")
        logger.info("=" * 50)

        self.ensure_schema(conn)

        load_order = ["products", "customers", "orders", "order_items", "payments"]
        counts: dict[str, int] = {}

        for name in load_order:
            raw_table = self._table_map[name]
            self.truncate_table(conn, raw_table)
            cnt = self.bulk_insert(conn, raw_table, data[name])
            counts[name] = cnt

        total = sum(counts.values())
        logger.info("Load complete: %d total rows into %s schema", total, self.schema)
        return counts
