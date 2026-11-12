import csv
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("products.csv")
OFFERS_PATH = Path(__file__).with_name("offers.csv")

FLOAT_FIELDS = ("price", "rating", "seller_rating")
INT_FIELDS = ("review_count", "warranty_months", "return_window_days")
OFFER_FLOAT_FIELDS = ("seller_rating", "price", "discount_percent", "shipping_cost")


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


def parse_offer(row):
    offer = {key: (value.strip() or None) for key, value in row.items()}
    for field in OFFER_FLOAT_FIELDS:
        if offer[field] is not None:
            offer[field] = float(offer[field])
    if offer["delivery_days"] is not None:
        offer["delivery_days"] = int(offer["delivery_days"])
    # Totals are computed here, not by the agents, so the LLM never does the arithmetic
    offer["sale_price"] = round(offer["price"] * (1 - (offer["discount_percent"] or 0) / 100), 2)
    # Unstated shipping makes the total unknown, not free
    offer["total_cost"] = (
        None if offer["shipping_cost"] is None else round(offer["sale_price"] + offer["shipping_cost"], 2)
    )
    return offer


@lru_cache(maxsize=1)
def _load_offers(path=OFFERS_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return tuple(parse_offer(row) for row in csv.DictReader(f))


def load_offers(product_id):
    """Every seller's offer for a product, cheapest known total first and unknown totals last."""
    offers = [dict(o) for o in _load_offers() if o["product_id"] == product_id]
    return sorted(offers, key=lambda o: (o["total_cost"] is None, o["total_cost"] or 0))


def with_offers(products):
    return [{**p, "offers": load_offers(p["product_id"])} for p in products]
