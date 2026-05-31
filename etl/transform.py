import logging
from typing import Any

logger = logging.getLogger(__name__)


class Transformer:
    def __init__(self, config: dict):
        self.config = config

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _trim(self, data: list[dict], fields: list[str]) -> list[dict]:
        for row in data:
            for f in fields:
                val = row.get(f)
                if val is not None:
                    row[f] = val.strip()
        return data

    def _lower(self, data: list[dict], fields: list[str]) -> list[dict]:
        for row in data:
            for f in fields:
                val = row.get(f)
                if val:
                    row[f] = val.lower()
        return data

    def _empty_to_null(self, data: list[dict]) -> list[dict]:
        for row in data:
            for k, v in row.items():
                if v is not None and v.strip() == "":
                    row[k] = None
        return data

    def _dedup(self, data: list[dict], key: str) -> list[dict]:
        seen: set[str] = set()
        clean: list[dict] = []
        for row in data:
            val = str(row.get(key, "") or "")
            if val not in seen:
                seen.add(val)
                clean.append(row)
            else:
                logger.warning("Duplicate %s='%s' removed (%d rows kept)", key, val, len(clean))
        return clean

    def _build_set(self, data: list[dict], key: str) -> set[str]:
        return {str(row.get(key, "") or "") for row in data}

    def _validate_fk(
        self,
        child_rows: list[dict],
        child_fk: str,
        parent_set: set[str],
        parent_name: str,
    ) -> list[dict]:
        valid: list[dict] = []
        for row in child_rows:
            val = str(row.get(child_fk, "") or "")
            if val in parent_set:
                valid.append(row)
            else:
                logger.warning(
                    "Orphan %s='%s' removed (not found in %s)", child_fk, val, parent_name
                )
        return valid

    # ------------------------------------------------------------------
    # Per-table transforms
    # ------------------------------------------------------------------

    def transform_products(self, data: list[dict]) -> list[dict]:
        data = self._trim(data, ["name", "category", "description"])
        data = self._lower(data, ["category"])
        data = self._empty_to_null(data)
        data = self._dedup(data, "product_id")
        return data

    def transform_customers(self, data: list[dict]) -> list[dict]:
        data = self._trim(data, ["first_name", "last_name", "email", "phone", "city", "state", "country"])
        data = self._lower(data, ["email", "country", "state"])
        data = self._empty_to_null(data)
        data = self._dedup(data, "customer_id")

        valid_statuses = {"active", "inactive", "suspended"}
        clean = []
        for row in data:
            st = (row.get("status") or "").strip().lower()
            if st in valid_statuses:
                row["status"] = st
                clean.append(row)
            else:
                logger.warning("Invalid status='%s' for customer %s, defaulting to active", st, row.get("customer_id"))
                row["status"] = "active"
                clean.append(row)
        data = clean

        return data

    def transform_orders(self, data: list[dict], valid_customer_ids: set[str]) -> list[dict]:
        data = self._trim(data, ["status", "shipping_address", "payment_method"])
        data = self._empty_to_null(data)
        data = self._dedup(data, "order_id")
        data = self._validate_fk(data, "customer_id", valid_customer_ids, "customers")
        return data

    def transform_order_items(
        self,
        data: list[dict],
        valid_order_ids: set[str],
        valid_product_ids: set[str],
    ) -> list[dict]:
        data = self._trim(data, [])
        data = self._empty_to_null(data)
        data = self._dedup(data, "order_item_id")
        data = self._validate_fk(data, "order_id", valid_order_ids, "orders")
        data = self._validate_fk(data, "product_id", valid_product_ids, "products")
        return data

    def transform_payments(self, data: list[dict], valid_order_ids: set[str]) -> list[dict]:
        data = self._trim(data, ["payment_method", "status", "transaction_id"])
        data = self._lower(data, ["payment_method", "status"])
        data = self._empty_to_null(data)
        data = self._dedup(data, "payment_id")
        data = self._validate_fk(data, "order_id", valid_order_ids, "orders")

        valid_statuses = {"paid", "failed", "pending", "refunded"}
        for row in data:
            st = row.get("status")
            if st not in valid_statuses:
                logger.warning("Invalid payment status='%s' for payment %s, defaulting to paid", st, row.get("payment_id"))
                row["status"] = "paid"
        return data

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def transform_all(self, raw: dict[str, list[dict]]) -> dict[str, list[dict]]:
        logger.info("=" * 50)
        logger.info("Transform phase")
        logger.info("=" * 50)

        products = self.transform_products(raw["products"])
        customers = self.transform_customers(raw["customers"])

        customer_ids = self._build_set(customers, "customer_id")
        orders = self.transform_orders(raw["orders"], customer_ids)

        order_ids = self._build_set(orders, "order_id")
        product_ids = self._build_set(products, "product_id")
        order_items = self.transform_order_items(raw["order_items"], order_ids, product_ids)

        payments = self.transform_payments(raw["payments"], order_ids)

        result = {
            "products": products,
            "customers": customers,
            "orders": orders,
            "order_items": order_items,
            "payments": payments,
        }

        for name, tbl in result.items():
            before = len(raw[name])
            after = len(tbl)
            if before != after:
                logger.info("  %-20s %6d -> %6d (%d removed)", name, before, after, before - after)
            else:
                logger.info("  %-20s %6d (unchanged)", name, after)

        return result
