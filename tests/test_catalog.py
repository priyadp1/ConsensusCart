from data.catalog import categories, get_product, load_products


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
