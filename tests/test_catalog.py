from data.catalog import categories, get_product, load_offers, load_products, with_offers


def test_catalog_has_categories_with_products():
    assert categories() == ["Coffee Makers", "Headphones", "Laptops"]
    for category in categories():
        assert len(load_products(category)) >= 5


def test_product_ids_are_unique():
    ids = [p["product_id"] for p in load_products()]
    assert len(ids) == len(set(ids))


def test_products_are_parsed_into_typed_fields():
    product = get_product("HP-02")
    assert product["price"] == 149.0
    assert product["review_count"] == 1210
    assert product["features"] == ["Active noise cancelling", "40h battery", "USB-C fast charge"]


def test_missing_values_are_none_not_zero():
    # The Trust Agent must see missing warranties as missing, not as a 0-month warranty
    assert get_product("HP-05")["warranty_months"] is None


def test_load_products_returns_copies():
    load_products()[0]["price"] = 0
    assert load_products()[0]["price"] > 0


def test_every_product_has_an_offer_from_its_catalog_seller_at_the_catalog_price():
    # Checkout charges the catalog price, so the catalog seller's offer must match it exactly
    for product in load_products():
        own = [o for o in load_offers(product["product_id"]) if o["seller"] == product["seller"]]
        assert len(own) == 1, product["product_id"]
        assert own[0]["total_cost"] == product["price"]


def test_offer_totals_apply_discount_then_shipping():
    offer = next(o for o in load_offers("HP-04") if o["seller"] == "SoundHub Outlet")
    assert offer["sale_price"] == 179.10      # $199.00 - 10%
    assert offer["total_cost"] == 191.60      # + $12.50 shipping


def test_unstated_shipping_makes_total_unknown_and_sorts_last():
    offers = load_offers("HP-01")
    assert offers[-1]["seller"] == "DealZone Marketplace"
    assert offers[-1]["shipping_cost"] is None
    assert offers[-1]["total_cost"] is None
    known = [o["total_cost"] for o in offers[:-1]]
    assert known == sorted(known)


def test_with_offers_attaches_offers_without_changing_products():
    products = load_products("Headphones")
    enriched = with_offers(products)
    assert "offers" not in products[0]
    assert enriched[0]["offers"] == load_offers(products[0]["product_id"])
