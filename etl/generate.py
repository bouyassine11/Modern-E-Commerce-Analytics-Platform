#!/usr/bin/env python3
"""
E-Commerce Data Generator

Generates realistic, referentially-integrated CSV datasets:
products, customers, orders, order_items, and payments.

Usage:
    python -m etl.generate
    python -m etl.generate --seed 123 --output-dir data/raw
"""

import argparse
import logging
import random
import sys
from pathlib import Path

from etl.config import load_config
from etl.utils import setup_logging, write_csv

from etl.generators.product_generator import generate_products
from etl.generators.customer_generator import generate_customers
from etl.generators.order_generator import generate_orders
from etl.generators.order_item_generator import generate_order_items
from etl.generators.payment_generator import generate_payments

logger = logging.getLogger("etl.generate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate realistic e-commerce CSV datasets",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory from config",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override random seed from config",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate data but do not write CSVs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    setup_logging(level=getattr(logging, args.log_level.upper()))
    logger.info("Starting e-commerce data generation")

    config = load_config(args.config)

    if args.output_dir:
        config["data"]["output_dir"] = args.output_dir
    if args.seed is not None:
        config["generation"]["seed"] = args.seed

    random.seed(config["generation"]["seed"])

    # Phase 1: Generate dimension entities (no dependencies)
    products = generate_products(config)
    customers = generate_customers(config)

    # Phase 2: Generate orders (depends on customer IDs)
    orders = generate_orders(config, customers)

    # Phase 3: Generate order items (depends on orders, products)
    order_items, order_totals = generate_order_items(config, orders, products)

    # Phase 4: Update order totals from computed items
    for order in orders:
        order["total_amount"] = order_totals[order["order_id"]]

    # Phase 5: Generate payments (depends on orders and their totals)
    payments = generate_payments(config, orders, order_totals)

    # Summary
    logger.info("=" * 50)
    logger.info("Generation Summary")
    logger.info("=" * 50)
    logger.info("  Products:     %6d", len(products))
    logger.info("  Customers:    %6d", len(customers))
    logger.info("  Orders:       %6d", len(orders))
    logger.info("  Order Items:  %6d", len(order_items))
    logger.info("  Payments:     %6d", len(payments))
    logger.info("=" * 50)

    if args.dry_run:
        logger.info("Dry run complete — no files written")
        return

    # Write all CSV files
    output_dir = config["data"]["output_dir"]
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    files = [
        write_csv("products.csv", products, output_dir),
        write_csv("customers.csv", customers, output_dir),
        write_csv("orders.csv", orders, output_dir),
        write_csv("order_items.csv", order_items, output_dir),
        write_csv("payments.csv", payments, output_dir),
    ]

    logger.info("All files written to: %s", output_dir)
    for f in files:
        logger.info("  ✔ %s", f)

    logger.info("Data generation complete")


if __name__ == "__main__":
    main()
