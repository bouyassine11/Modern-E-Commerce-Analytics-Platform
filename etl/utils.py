import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def setup_logging(log_dir: str = "logs", level: int = logging.INFO) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(log_dir) / f"generate_{timestamp}.log"

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def write_csv(filename: str, data: list[dict], output_dir: str) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = Path(output_dir) / filename

    if not data:
        logging.getLogger(__name__).warning("No data to write for %s", filename)
        return ""

    with open(filepath, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)

    size_kb = filepath.stat().st_size / 1024
    logging.getLogger(__name__).info(
        "Wrote %d rows → %s (%.1f KB)", len(data), filepath, size_kb
    )
    return str(filepath)
