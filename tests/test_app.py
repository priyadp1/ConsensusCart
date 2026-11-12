from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from payments import paypal
from tests.test_consensus import scripted  # noqa: F401  (fixture)

APP_PATH = str(Path(__file__).parent.parent / "app.py")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # Empty rather than deleted, so load_dotenv() can't fill them in from a real .env
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "")


def search(category="Headphones", budget=200):
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    at.selectbox[0].set_value(category)
    at.text_input[0].input("Noise cancelling headphones for commuting")
    at.number_input[0].set_value(budget)
    at.button[0].click()
    return at.run()


def page_text(at):
    elements = [*at.markdown, *at.caption, *at.warning]
    return "\n".join(str(element.value) for element in elements)


def test_search_runs_the_real_graph_and_shows_consensus(scripted):
    scripted({"budget": ["HP-03"], "quality": ["HP-04"], "trust": ["HP-04"]})
    at = search()
    assert not at.exception
    text = page_text(at)
    assert "Nordvik Quiet 700" in text                   # consensus pick
    assert "Budget Agent dissents" in text               # persistent dissent is surfaced
    assert at.metric[0].value == "67%"
    assert "PayPal checkout is disabled" in at.info[0].value


def test_agent_that_changes_its_mind_is_flagged(scripted):
    scripted({"budget": ["HP-03", "HP-04"], "quality": ["HP-04"], "trust": ["HP-04"]})
    at = search()
    assert not at.exception
    assert "Changed its mind" in page_text(at)
    assert at.metric[0].value == "100%"


def test_changing_the_search_hides_old_results(scripted):
    scripted({"budget": ["HP-04"], "quality": ["HP-04"], "trust": ["HP-04"]})
    at = search()
    assert "Nordvik Quiet 700" in page_text(at)
    at.selectbox[0].set_value("Coffee Makers")
    at.run()
    assert not at.exception
    assert "Nordvik Quiet 700" not in page_text(at)
    assert "Your search changed" in at.info[0].value


def test_no_products_in_budget_shows_error(scripted):
    scripted({"budget": ["HP-06"], "quality": ["HP-06"], "trust": ["HP-06"]})
    at = search(budget=10)
    assert not at.exception
    assert "No products within budget" in at.error[0].value


def test_checkout_creates_paypal_order(scripted, monkeypatch):
    scripted({"budget": ["HP-04"], "quality": ["HP-04"], "trust": ["HP-04"]})
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
    created = []

    def create_order(product, return_url, cancel_url):
        created.append(product["product_id"])
        return {"id": "ORDER123", "status": "PAYER_ACTION_REQUIRED", "approve_url": "https://paypal/approve"}

    monkeypatch.setattr(paypal, "create_order", create_order)
    at = search()
    next(b for b in at.button if b.label.startswith("Buy with PayPal")).click()
    at.run()
    assert not at.exception
    assert created == ["HP-04"]
    assert "ORDER123" in page_text(at)


def test_paypal_return_captures_and_shows_receipt(monkeypatch):
    captured = []

    def capture_order(order_id):
        captured.append(order_id)
        return {"order_id": order_id, "status": "COMPLETED", "capture_id": "CAP1", "capture_status": "COMPLETED",
                "amount": "189.00", "currency": "USD", "product_id": "HP-04",
                "payer_name": "Sam Buyer", "payer_email": None}

    monkeypatch.setattr(paypal, "capture_order", capture_order)
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.query_params["token"] = "ORDER123"
    at.query_params["PayerID"] = "PAYER1"
    at.run()
    assert not at.exception
    assert captured == ["ORDER123"]
    assert "Payment complete" in at.success[0].value
    assert at.metric[0].value == "Nordvik Quiet 700"


def test_paypal_cancel_does_not_capture(monkeypatch):
    monkeypatch.setattr(paypal, "capture_order", lambda order_id: pytest.fail("should not capture"))
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.query_params["token"] = "ORDER123"
    at.query_params["cancelled"] = "true"
    at.run()
    assert not at.exception
    assert "cancelled" in at.warning[0].value
