import logging
import random
from datetime import datetime, timedelta

from faker import Faker

logger = logging.getLogger(__name__)

# Order status distribution for orders older than 30 days
MATURE_STATUS_WEIGHTS = {
    "delivered": 0.90,
    "shipped": 0.00,
    "processing": 0.00,
    "cancelled": 0.07,
    "refunded": 0.03,
}

# Order status distribution for orders 4–30 days old
RECENT_STATUS_WEIGHTS = {
    "delivered": 0.75,
    "shipped": 0.10,
    "processing": 0.05,
    "cancelled": 0.07,
    "refunded": 0.03,
}

# Order status distribution for orders less than 4 days old
FRESH_STATUS_WEIGHTS = {
    "delivered": 0.10,
    "shipped": 0.35,
    "processing": 0.40,
    "cancelled": 0.12,
    "refunded": 0.03,
}


def _parse_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str)


def _random_date(start: datetime, end: datetime) -> datetime:
    """Generate a random date between start and end, biased toward recent."""
    seconds = (end - start).total_seconds()
    # Square the random value for recency bias
    t = random.random() ** 1.5
    return start + timedelta(seconds=t * seconds)


def _assign_status(order_date: datetime) -> str:
    now = datetime.now()
    days_ago = (now - order_date).days

    if days_ago <= 3:
        weights = FRESH_STATUS_WEIGHTS
    elif days_ago <= 30:
        weights = RECENT_STATUS_WEIGHTS
    else:
        weights = MATURE_STATUS_WEIGHTS

    return random.choices(
        list(weights.keys()),
        weights=list(weights.values()),
    )[0]


def _customer_weights(num_customers: int) -> list[float]:
    """Pareto-like weights: top 20% of customers get ~80% of the weight."""
    return [1.0 / (i + 1) ** 0.6 for i in range(num_customers)]


def generate_orders(config: dict, customers: list[dict]) -> list[dict]:
    logger.info("Generating orders...")
    seed = config["generation"]["seed"]
    num = config["generation"]["orders"]

    Faker.seed(seed + 1)
    faker = Faker("en_US")
    random.seed(seed + 1)

    start = _parse_date(config["generation"]["date_range"]["start"])
    end = _parse_date(config["generation"]["date_range"]["end"])

    customer_ids = [c["customer_id"] for c in customers]
    weights = _customer_weights(len(customer_ids))

    orders: list[dict] = []

    for order_id in range(1, num + 1):
        customer_id = random.choices(customer_ids, weights=weights)[0]
        order_date = _random_date(start, end)
        status = _assign_status(order_date)

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": order_date.isoformat(),
                "status": status,
                "total_amount": 0.0,
                "shipping_address": faker.street_address(),
                "payment_method": "",
            }
        )

    logger.info("Generated %d orders", len(orders))
    return orders
