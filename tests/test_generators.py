from etl.generators.customer_generator import generate_customers
from etl.generators.order_generator import generate_orders
from etl.generators.order_item_generator import generate_order_items
from etl.generators.payment_generator import generate_payments
from etl.generators.product_generator import generate_products


class TestProductGenerator:
    def test_generates_correct_count(self, sample_config):
        products = generate_products(sample_config)
        assert len(products) == sample_config["generation"]["products"]

    def test_all_have_required_fields(self, sample_config):
        products = generate_products(sample_config)
        for p in products:
            assert p["product_id"]
            assert p["name"]
            assert p["category"]
            assert p["price"]
            assert p["stock_quantity"]

    def test_prices_within_category_range(self, sample_config):
        products = generate_products(sample_config)
        for p in products:
            price = float(p["price"])
            cat_config = sample_config["categories"][p["category"]]
            assert cat_config["price_range"][0] <= price <= cat_config["price_range"][1]

    def test_unique_product_ids(self, sample_config):
        products = generate_products(sample_config)
        ids = [p["product_id"] for p in products]
        assert len(ids) == len(set(ids))


class TestCustomerGenerator:
    def test_generates_correct_count(self, sample_config):
        customers = generate_customers(sample_config)
        assert len(customers) == sample_config["generation"]["customers"]

    def test_all_have_required_fields(self, sample_config):
        customers = generate_customers(sample_config)
        for c in customers:
            assert c["customer_id"]
            assert "@" in c["email"]
            assert c["country"]

    def test_unique_customer_ids(self, sample_config):
        customers = generate_customers(sample_config)
        ids = [c["customer_id"] for c in customers]
        assert len(ids) == len(set(ids))


class TestOrderGenerator:
    def test_generates_correct_count(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        assert len(orders) == sample_config["generation"]["orders"]

    def test_all_reference_valid_customers(self, sample_config):
        customers = generate_customers(sample_config)
        customer_ids = {c["customer_id"] for c in customers}
        orders = generate_orders(sample_config, customers)
        for o in orders:
            assert o["customer_id"] in customer_ids

    def test_unique_order_ids(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        ids = [o["order_id"] for o in orders]
        assert len(ids) == len(set(ids))

    def test_dates_within_range(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        start = sample_config["generation"]["date_range"]["start"]
        end = sample_config["generation"]["date_range"]["end"]
        for o in orders:
            assert start <= o["order_date"] <= end


class TestOrderItemGenerator:
    def test_generates_correct_count(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        products = generate_products(sample_config)
        items, totals = generate_order_items(sample_config, orders, products)
        assert len(items) == sample_config["generation"]["order_items"]

    def test_all_reference_valid_orders_and_products(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        products = generate_products(sample_config)
        items, totals = generate_order_items(sample_config, orders, products)
        order_ids = {o["order_id"] for o in orders}
        product_ids = {p["product_id"] for p in products}
        for i in items:
            assert i["order_id"] in order_ids
            assert i["product_id"] in product_ids

    def test_totals_match_item_sums(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        products = generate_products(sample_config)
        items, totals = generate_order_items(sample_config, orders, products)
        for o in orders:
            oid = o["order_id"]
            item_sum = sum(
                int(i["quantity"]) * float(i["unit_price"])
                for i in items if i["order_id"] == oid
            )
            assert abs(totals[oid] - item_sum) < 0.01


class TestPaymentGenerator:
    def test_generates_correct_count(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        products = generate_products(sample_config)
        items, order_totals = generate_order_items(sample_config, orders, products)
        for o in orders:
            o["total_amount"] = order_totals[o["order_id"]]
        payments = generate_payments(sample_config, orders, order_totals)
        assert len(payments) == sample_config["generation"]["payments"]

    def test_refunds_negative_amount(self, sample_config):
        customers = generate_customers(sample_config)
        orders = generate_orders(sample_config, customers)
        products = generate_products(sample_config)
        items, order_totals = generate_order_items(sample_config, orders, products)
        for o in orders:
            o["total_amount"] = order_totals[o["order_id"]]
        payments = generate_payments(sample_config, orders, order_totals)
        for p in payments:
            if p["status"] == "refunded":
                assert float(p["amount"]) < 0
