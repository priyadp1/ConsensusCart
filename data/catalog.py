import csv
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("products.csv")

FLOAT_FIELDS = ("price", "rating", "seller_rating")
INT_FIELDS = ("review_count", "warranty_months", "return_window_days")


def parse_product(row):
    # Empty cells become None so the agents see the information as missing, not as zero
    product = {key: (value.strip() or None) for key, value in row.items()}
    for field in FLOAT_FIELDS:
        if product[field] is not None:
            product[field] = float(product[field])
    for field in INT_FIELDS:
        if product[field] is not None:
            product[field] = int(product[field])
    product["features"] = [f.strip() for f in (product["features"] or "").split(";") if f.strip()]
    return product


@lru_cache(maxsize=1)
def _load_catalog(path=CATALOG_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return tuple(parse_product(row) for row in csv.DictReader(f))


def load_products(category=None):
    products = [dict(p) for p in _load_catalog()]
    if category:
        products = [p for p in products if p["category"] == category]
    return products


def categories():
    return sorted({p["category"] for p in _load_catalog()})


def get_product(product_id):
    return next((dict(p) for p in _load_catalog() if p["product_id"] == product_id), None)
