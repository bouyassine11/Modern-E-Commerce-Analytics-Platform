import os

import yaml
from pathlib import Path


def load_config(path: str = "config.yaml") -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)

    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: dict) -> None:
    db = config.setdefault("database", {})
    db["host"] = os.environ.get("PGHOST", db.get("host", "localhost"))
    db["port"] = int(os.environ.get("PGPORT", db.get("port", 5432)))
    db["dbname"] = os.environ.get("PGDATABASE", db.get("dbname", "ecommerce"))
    db["user"] = os.environ.get("PGUSER", db.get("user", "postgres"))
    db["password"] = os.environ.get("PGPASSWORD", db.get("password", "postgres"))
    db["schema"] = os.environ.get("PGSCHEMA", db.get("schema", "raw"))

    gen = config.setdefault("generation", {})
    gen["seed"] = int(os.environ.get("ETL_SEED", gen.get("seed", 42)))

    data = config.setdefault("data", {})
    data["output_dir"] = os.environ.get("ETL_DATA_DIR", data.get("output_dir", "data/raw"))
