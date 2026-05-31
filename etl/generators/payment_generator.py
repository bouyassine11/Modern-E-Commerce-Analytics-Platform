import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

PAYMENT_METHOD_WEIGHTS = {
    "credit_card": 0.45,
    "paypal": 0.25,
    "stripe": 0.20,
    "bank_transfer": 0.10,
}

PAYMENT_STATUS_WEIGHTS = {
    "paid": 0.88,
    "failed": 0.05,
    "pending": 0.05,
    "refunded": 0.02,
}


def _generate_transaction_id() -> str:
    prefix = random.choice(["TXN", "PAY", "CH", "REF"])
    num = random.randint(10000000, 99999999)
    return f"{prefix}-{num}"


def generate_payments(
    config: dict,
    orders: list[dict],
    order_totals: dict[int, float],
) -> list[dict]:
    logger.info("Generating payments...")
    seed = config["generation"]["seed"]
    random.seed(seed + 3)

    payments: list[dict] = []
    now = datetime.now()
    payment_id = 1

    for order in orders:
        order_id = order["order_id"]
        order_date = datetime.fromisoformat(order["order_date"])
        total_amount = order_totals[order_id]

        status = random.choices(
            list(PAYMENT_STATUS_WEIGHTS.keys()),
            weights=list(PAYMENT_STATUS_WEIGHTS.values()),
        )[0]

        method = random.choices(
            list(PAYMENT_METHOD_WEIGHTS.keys()),
            weights=list(PAYMENT_METHOD_WEIGHTS.values()),
        )[0]

        if status == "paid":
            amount = total_amount
            # Payment happens shortly after order
            payment_date = order_date
        elif status == "failed":
            amount = total_amount
            payment_date = order_date
        elif status == "pending":
            amount = total_amount
            payment_date = order_date
        elif status == "refunded":
            amount = round(-total_amount, 2)
            refund_days = random.randint(7, 30)
            payment_date = order_date + timedelta(days=refund_days)
        else:
            amount = total_amount
            payment_date = order_date

        payments.append(
            {
                "payment_id": payment_id,
                "order_id": order_id,
                "payment_date": payment_date.isoformat(),
                "amount": amount,
                "payment_method": method,
                "status": status,
                "transaction_id": _generate_transaction_id(),
            }
        )
        payment_id += 1

    logger.info("Generated %d payments", len(payments))
    return payments
