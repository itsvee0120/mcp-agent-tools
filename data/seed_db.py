"""Create and seed data/enterprise_ops.db (customers, products, inventory, orders)."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "enterprise_ops.db"

SCHEMA = """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL
);
CREATE TABLE products (
    sku        TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    unit_price REAL NOT NULL
);
CREATE TABLE inventory (
    inventory_id   INTEGER PRIMARY KEY,
    sku            TEXT NOT NULL REFERENCES products(sku),
    warehouse_city TEXT NOT NULL,
    quantity       INTEGER NOT NULL
);
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    sku         TEXT NOT NULL REFERENCES products(sku),
    quantity    INTEGER NOT NULL,
    order_value REAL NOT NULL,
    status      TEXT NOT NULL,
    order_date  TEXT NOT NULL
);
"""

CUSTOMERS = [
    (1, "Cascade Outfitters", "Seattle"),
    (2, "Pike Street Supply", "Seattle"),
    (3, "Rose City Retail", "Portland"),
    (4, "Bay Area Logistics", "San Francisco"),
    (5, "Lone Star Goods", "Austin"),
    (6, "Windy City Traders", "Chicago"),
    (7, "Empire Distribution", "New York"),
    (8, "Mile High Mercantile", "Denver"),
]

PRODUCTS = [
    ("SKU-90210", "Industrial Pallet Wrap", 89.50),
    ("SKU-10001", "Corrugated Box (Large)", 2.75),
    ("SKU-10002", "Corrugated Box (Small)", 1.40),
    ("SKU-20450", "Packing Tape Roll", 3.10),
    ("SKU-30777", "Bubble Wrap Roll", 24.99),
    ("SKU-41200", "Shipping Label Pack", 12.00),
    ("SKU-55010", "Hand Pallet Jack", 349.00),
    ("SKU-60300", "Stretch Film Dispenser", 45.25),
]

INVENTORY = [
    (1, "SKU-90210", "Seattle", 150),
    (2, "SKU-90210", "Portland", 40),
    (3, "SKU-90210", "Chicago", 0),
    (4, "SKU-10001", "Seattle", 2000),
    (5, "SKU-10002", "Seattle", 3500),
    (6, "SKU-20450", "Portland", 800),
    (7, "SKU-30777", "San Francisco", 120),
    (8, "SKU-41200", "Austin", 300),
    (9, "SKU-55010", "Chicago", 15),
    (10, "SKU-60300", "New York", 60),
    (11, "SKU-55010", "Seattle", 4),
    (12, "SKU-30777", "Denver", 75),
]

ORDERS = [
    (4485, 3, "SKU-20450", 200, 620.00, "shipped", "2026-11-02"),
    (4486, 4, "SKU-30777", 30, 749.70, "shipped", "2026-11-03"),
    (4487, 5, "SKU-41200", 50, 600.00, "delivered", "2026-11-04"),
    (4488, 6, "SKU-55010", 2, 698.00, "shipped", "2026-11-05"),
    (4489, 7, "SKU-60300", 10, 452.50, "pending", "2026-11-07"),
    (4490, 8, "SKU-30777", 20, 499.80, "pending", "2026-11-09"),
    (4491, 2, "SKU-10001", 500, 1375.00, "shipped", "2026-11-10"),
    (4492, 1, "SKU-90210", 120, 10740.00, "pending", "2026-11-15"),
    (4493, 2, "SKU-10002", 1000, 1400.00, "pending", "2026-11-15"),
    (4494, 1, "SKU-55010", 3, 1047.00, "pending", "2026-11-16"),
    (4495, 3, "SKU-90210", 25, 2237.50, "pending", "2026-11-16"),
    (4496, 6, "SKU-20450", 100, 310.00, "cancelled", "2026-11-16"),
]


def main() -> None:
    """Recreate the database from scratch with seed data."""
    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", CUSTOMERS)
        conn.executemany("INSERT INTO products VALUES (?, ?, ?)", PRODUCTS)
        conn.executemany("INSERT INTO inventory VALUES (?, ?, ?, ?)", INVENTORY)
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", ORDERS)
    conn.close()
    print(f"Seeded {DB_PATH.name}")


if __name__ == "__main__":
    main()
