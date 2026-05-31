from etl.transform import Transformer


class TestTransformer:
    def setup_method(self):
        self.transformer = Transformer({})

    def test_trim_whitespace(self):
        data = [{"name": "  hello  ", "city": "  NYC"}]
        result = self.transformer._trim(data, ["name", "city"])
        assert result[0]["name"] == "hello"
        assert result[0]["city"] == "NYC"

    def test_lowercase_fields(self):
        data = [{"email": "JOHN@EXAMPLE.COM", "country": "US"}]
        result = self.transformer._lower(data, ["email"])
        assert result[0]["email"] == "john@example.com"
        assert result[0]["country"] == "US"

    def test_empty_to_null(self):
        data = [{"a": "  ", "b": "val", "c": None}]
        result = self.transformer._empty_to_null(data)
        assert result[0]["a"] is None
        assert result[0]["b"] == "val"
        assert result[0]["c"] is None

    def test_dedup_removes_duplicates(self):
        data = [
            {"id": "1", "name": "first"},
            {"id": "2", "name": "second"},
            {"id": "1", "name": "duplicate"},
        ]
        result = self.transformer._dedup(data, "id")
        assert len(result) == 2
        assert result[0]["name"] == "first"

    def test_dedup_keeps_first_occurrence(self, sample_products):
        result = self.transformer._dedup(sample_products, "product_id")
        assert len(result) == 3
        assert result[0]["product_id"] == "1"
        assert "Laptop" in result[0]["name"]

    def test_validate_fk_removes_orphans(self):
        child = [{"id": "1", "parent_id": "A"}, {"id": "2", "parent_id": "B"}, {"id": "3", "parent_id": "Z"}]
        parent_set = {"A", "B"}
        result = self.transformer._validate_fk(child, "parent_id", parent_set, "parents")
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"

    def test_transform_products(self, sample_products):
        result = self.transformer.transform_products(sample_products)
        assert len(result) == 3
        assert result[0]["name"] == "Laptop"
        assert result[1]["stock_quantity"] is None

    def test_transform_customers_valid_status(self, sample_customers):
        result = self.transformer.transform_customers(sample_customers)
        assert len(result) == 3
        for c in result:
            assert c["status"] in ("active", "inactive")

    def test_transform_customers_trim_and_lower(self, sample_customers):
        result = self.transformer.transform_customers(sample_customers)
        assert result[0]["first_name"] == "John"
        assert result[0]["email"] == "john@example.com"

    def test_transform_orders_removes_orphan(self, sample_orders, sample_customers):
        customer_ids = {c["customer_id"] for c in sample_customers}
        result = self.transformer.transform_orders(sample_orders, customer_ids)
        assert len(result) == 2
        assert all(o["customer_id"] in customer_ids for o in result)

    def test_transform_order_items_removes_orphans(self, sample_order_items, sample_orders, sample_products):
        order_ids = {o["order_id"] for o in sample_orders}
        product_ids = {p["product_id"] for p in sample_products}
        result = self.transformer.transform_order_items(sample_order_items, order_ids, product_ids)
        # Should remove order_item 1004 (order_id=999) and 1005 (product_id=99)
        assert len(result) == 3

    def test_transform_payments_normalizes_status(self, sample_payments):
        result = self.transformer.transform_payments(sample_payments, {"101", "102"})
        assert result[1]["payment_method"] == "paypal"
        assert result[1]["status"] == "paid"

    def test_transform_all_pipeline(self, sample_config, sample_products, sample_customers, sample_orders, sample_order_items, sample_payments):
        transformer = Transformer(sample_config)
        raw = {
            "products": sample_products,
            "customers": sample_customers,
            "orders": sample_orders,
            "order_items": sample_order_items,
            "payments": sample_payments,
        }
        result = transformer.transform_all(raw)
        assert set(result.keys()) == {"products", "customers", "orders", "order_items", "payments"}
        assert len(result["products"]) == 3
        assert len(result["customers"]) == 3
        assert len(result["orders"]) == 2
        assert len(result["order_items"]) == 3
        assert len(result["payments"]) == 2
