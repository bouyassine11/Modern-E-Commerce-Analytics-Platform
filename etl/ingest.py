#!/usr/bin/env python3
"""
ETL Pipeline — Extract, Transform, Load

Reads CSV files, cleans/validates them, and bulk-loads into PostgreSQL.
All phases are logged to the monitoring.etl_runs + monitoring.etl_task_runs
audit tables for observability.

Usage:
    python -m etl.ingest
    python -m etl.ingest --config config.yaml --log-level DEBUG
    python -m etl.ingest --dry-run
"""

import argparse
import logging
import sys

from etl.config import load_config
from etl.utils import setup_logging, timed
from etl.extract import Extractor
from etl.transform import Transformer
from etl.load import Loader
from etl.utils import get_connection
from etl.monitor import PipelineLogger

logger = logging.getLogger("etl.ingest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ETL pipeline for e-commerce analytics")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--dry-run", action="store_true", help="Skip database load")
    return parser.parse_args()


@timed
def run_pipeline(config: dict, dry_run: bool = False) -> dict:
    extractor = Extractor(config)
    transformer = Transformer(config)
    loader = Loader(config)

    with PipelineLogger(config["database"]) as monitor:
        monitor.start_run(pipeline_name="etl_ingest")
        run_id = monitor.run_id

        try:
            # Phase 1 — Extract
            logger.info("Phase 1/3: Extract")
            raw = extractor.extract_all(monitor=monitor, run_id=run_id)

            extracted_total = sum(len(v) for v in raw.values())

            # Phase 2 — Transform
            logger.info("Phase 2/3: Transform")
            clean = transformer.transform_all(raw, monitor=monitor, run_id=run_id)

            # Phase 3 — Load
            logger.info("Phase 3/3: Load")
            if dry_run:
                logger.info("Dry-run mode — skipping database load")
                for name, rows in clean.items():
                    logger.info("  Would load %d rows into %s", len(rows), f"{config['database']['schema']}.{name}_raw")
                monitor.complete_run(rows_extracted=extracted_total)
                return {name: len(rows) for name, rows in clean.items()}

            conn = get_connection(config["database"])
            try:
                with conn:
                    counts = loader.load_all(conn, clean, monitor=monitor, run_id=run_id)
            finally:
                conn.close()

            loaded_total = sum(counts.values())
            monitor.complete_run(
                rows_extracted=extracted_total,
                rows_loaded=loaded_total,
            )
            return counts

        except Exception as exc:
            monitor.fail_run(error_message=str(exc))
            raise


def main() -> None:
    args = parse_args()
    setup_logging(level=getattr(logging, args.log_level.upper()))
    logger.info("ETL pipeline starting")

    config = load_config(args.config)

    try:
        counts = run_pipeline(config, dry_run=args.dry_run)

        logger.info("=" * 50)
        logger.info("Pipeline Summary")
        logger.info("=" * 50)
        for name, cnt in counts.items():
            logger.info("  %-20s %6d", name, cnt)
        logger.info("=" * 50)
        logger.info("ETL pipeline finished successfully")

    except Exception:
        logger.exception("ETL pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
