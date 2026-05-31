import logging
import random
from datetime import datetime

from faker import Faker

logger = logging.getLogger(__name__)

CUSTOMER_STATUS_WEIGHTS = {
    "active": 0.85,
    "inactive": 0.10,
    "suspended": 0.05,
}


def _generate_phone(faker: Faker) -> str:
    return faker.phone_number()


def _generate_email(faker: Faker, first_name: str, last_name: str) -> str:
    domains = [
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "protonmail.com",
        "icloud.com",
        "hotmail.com",
    ]
    domain = random.choice(domains)
    variants = [
        f"{first_name.lower()}.{last_name.lower()}",
        f"{first_name.lower()}{last_name.lower()}",
        f"{first_name[0].lower()}{last_name.lower()}",
        f"{last_name.lower()}.{first_name.lower()}",
    ]
    return f"{random.choice(variants)}@{domain}"


def generate_customers(config: dict) -> list[dict]:
    logger.info("Generating customers...")
    seed = config["generation"]["seed"]
    num = config["generation"]["customers"]

    Faker.seed(seed)
    faker = Faker("en_US")
    random.seed(seed)

    now = datetime.now()
    signup_end = now
    signup_start = datetime(2020, 1, 1)

    customers: list[dict] = []

    for customer_id in range(1, num + 1):
        first_name = faker.first_name()
        last_name = faker.last_name()
        status = random.choices(
            list(CUSTOMER_STATUS_WEIGHTS.keys()),
            weights=list(CUSTOMER_STATUS_WEIGHTS.values()),
        )[0]
        signup_date = faker.date_between(start_date=signup_start, end_date=signup_end)

        customers.append(
            {
                "customer_id": customer_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": _generate_email(faker, first_name, last_name),
                "phone": _generate_phone(faker),
                "address": faker.street_address(),
                "city": faker.city(),
                "state": faker.state(),
                "zip_code": faker.zipcode(),
                "country": "USA",
                "signup_date": signup_date.isoformat(),
                "status": status,
            }
        )

    logger.info("Generated %d customers", len(customers))
    return customers
