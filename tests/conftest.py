from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    return FIXTURES_DIR


@pytest.fixture
def sample_config() -> dict:
    return {
        "database": {
            "host": "localhost",
            "port": 5432,
            "dbname": "ecommerce",
            "user": "postgres",
            "password": "postgres",
            "schema": "raw",
        },
        "etl": {
            "file_map": {
                "products": "products.csv",
                "customers": "customers.csv",
                "orders": "orders.csv",
                "order_items": "order_items.csv",
                "payments": "payments.csv",
            },
        },
        "data": {
            "output_dir": str(FIXTURES_DIR),
        },
        "generation": {
            "seed": 42,
            "customers": 100,
            "products": 20,
            "orders": 200,
            "order_items": 500,
            "payments": 200,
        },
    }


@pytest.fixture
def sample_products() -> list[dict]:
    return [
        {"product_id": "1", "name": "  Laptop  ", "category": "electronics", "price": "999.99", "stock_quantity": "10", "description": "High-end laptop", "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"product_id": "2", "name": "Mouse", "category": "electronics", "price": "29.99", "stock_quantity": "", "description": "Wireless mouse", "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"product_id": "3", "name": "  T-Shirt", "category": "Clothing", "price": "19.99", "stock_quantity": "50", "description": "Cotton T-shirt", "created_at": "2024-01-01", "updated_at": "2024-01-01"},
        {"product_id": "1", "name": "Laptop", "category": "electronics", "price": "999.99", "stock_quantity": "10", "description": "High-end laptop", "created_at": "2024-01-01", "updated_at": "2024-01-01"},
    ]


@pytest.fixture
def sample_customers() -> list[dict]:
    return [
        {"customer_id": "1", "first_name": "  John  ", "last_name": "Doe", "email": "  JOHN@example.com  ", "phone": "555-0100", "address": "123 Main St", "city": "New York", "state": "NY", "zip_code": "10001", "country": "US", "signup_date": "2024-01-15", "status": "active"},
        {"customer_id": "2", "first_name": "Jane", "last_name": "Smith", "email": "jane@example.com", "phone": "", "address": "456 Oak Ave", "city": "Los Angeles", "state": "CA", "zip_code": "90001", "country": "US", "signup_date": "2024-02-01", "status": "active"},
        {"customer_id": "3", "first_name": "Bob", "last_name": "Dupont", "email": "bob@france.fr", "phone": "555-0200", "address": "1 Rue de Paris", "city": "Paris", "state": "", "zip_code": "75001", "country": "FR", "signup_date": "2024-03-01", "status": "inactive"},
    ]


@pytest.fixture
def sample_orders(sample_customers) -> list[dict]:
    return [
        {"order_id": "101", "customer_id": "1", "order_date": "2024-06-01", "status": "delivered", "total_amount": "199.98", "shipping_address": "123 Main St", "payment_method": "credit_card"},
        {"order_id": "102", "customer_id": "2", "order_date": "2024-06-15", "status": "shipped", "total_amount": "59.98", "shipping_address": "456 Oak Ave", "payment_method": "paypal"},
        {"order_id": "103", "customer_id": "99", "order_date": "2024-06-20", "status": "processing", "total_amount": "29.99", "shipping_address": "Nowhere", "payment_method": "credit_card"},
    ]


@pytest.fixture
def sample_order_items(sample_orders, sample_products) -> list[dict]:
    return [
        {"order_item_id": "1001", "order_id": "101", "product_id": "1", "quantity": "1", "unit_price": "999.99", "total_price": "999.99"},
        {"order_item_id": "1002", "order_id": "101", "product_id": "2", "quantity": "2", "unit_price": "29.99", "total_price": "59.98"},
        {"order_item_id": "1003", "order_id": "102", "product_id": "3", "quantity": "3", "unit_price": "19.99", "total_price": "59.97"},
        {"order_item_id": "1004", "order_id": "999", "product_id": "1", "quantity": "1", "unit_price": "999.99", "total_price": "999.99"},
        {"order_item_id": "1005", "order_id": "103", "product_id": "99", "quantity": "1", "unit_price": "10.00", "total_price": "10.00"},
    ]


@pytest.fixture
def sample_payments(sample_orders) -> list[dict]:
    return [
        {"payment_id": "P001", "order_id": "101", "payment_date": "2024-06-01", "amount": "199.98", "payment_method": "credit_card", "status": "paid", "transaction_id": "TXN001"},
        {"payment_id": "P002", "order_id": "102", "payment_date": "2024-06-15", "amount": "59.98", "payment_method": "PayPal", "status": "paid", "transaction_id": "TXN002"},
        {"payment_id": "P003", "order_id": "101", "payment_date": "2024-07-01", "amount": "-199.98", "payment_method": "credit_card", "status": "refunded", "transaction_id": "TXN003"},
    ]
