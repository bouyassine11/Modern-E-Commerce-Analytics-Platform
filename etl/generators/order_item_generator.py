import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)


def _items_per_order() -> int:
    weights = {
        1: 0.15,
        2: 0.25,
        3: 0.20,
        4: 0.25,
        5: 0.15,
    }
    return random.choices(
        list(weights.keys()),
        weights=list(weights.values()),
    )[0]


def _quantity() -> int:
    return random.randint(1, 3)


def _product_weights(num_products: int) -> list[float]:
    """Zipf-like popularity distribution."""
    return [1.0 / (i + 1) ** 0.8 for i in range(num_products)]


def generate_order_items(
    config: dict,
    orders: list[dict],
    products: list[dict],
) -> tuple[list[dict], dict[int, float]]:
    logger.info("Generating order items...")
    seed = config["generation"]["seed"]
    random.seed(seed + 2)

    product_ids = [p["product_id"] for p in products]
    product_prices = {p["product_id"]: p["price"] for p in products}
    prod_weights = _product_weights(len(product_ids))

    order_items: list[dict] = []
    order_totals: dict[int, float] = {o["order_id"]: 0.0 for o in orders}
    order_item_id = 1

    for order in orders:
        order_id = order["order_id"]
        num_items = _items_per_order()

        for _ in range(num_items):
            product_id = random.choices(product_ids, weights=prod_weights)[0]
            qty = _quantity()
            unit_price = product_prices[product_id]
            total_price = round(qty * unit_price, 2)

            order_items.append(
                {
                    "order_item_id": order_item_id,
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_price": total_price,
                }
            )
            order_totals[order_id] += total_price
            order_item_id += 1

    # Round totals to 2 decimal places
    for order_id in order_totals:
        order_totals[order_id] = round(order_totals[order_id], 2)

    logger.info("Generated %d order items across %d orders", len(order_items), len(orders))
    return order_items, order_totals
