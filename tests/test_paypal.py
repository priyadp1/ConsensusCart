import pytest
from payments import paypal

PRODUCT = {"product_id": "HP-02", "name": "Tempo Wave 2", "price": 149.0}


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body
        self.text = str(body)

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self.body


@pytest.fixture
def fake_paypal(monkeypatch):
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
    calls = []
    responses = {}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/v1/oauth2/token"):
            return FakeResponse(200, {"access_token": "token-123"})
        return responses[url.rsplit("/v2/", 1)[1]]

    monkeypatch.setattr(paypal.requests, "post", post)
    return calls, responses


def test_order_request_uses_catalog_price_and_product_id():
    body = paypal.build_order_request(PRODUCT, "http://app", "http://app/?cancelled=true")
    unit = body["purchase_units"][0]
    assert body["intent"] == "CAPTURE"
    assert unit["reference_id"] == "HP-02"
    assert unit["amount"] == {"currency_code": "USD", "value": "149.00"}
    assert body["payment_source"]["paypal"]["experience_context"]["return_url"] == "http://app"


def test_create_order_returns_approval_link(fake_paypal):
    calls, responses = fake_paypal
    responses["checkout/orders"] = FakeResponse(200, {
        "id": "5O190127TN364715T",
        "status": "PAYER_ACTION_REQUIRED",
        "links": [
            {"rel": "self", "href": "https://api/self"},
            {"rel": "payer-action", "href": "https://sandbox.paypal.com/checkoutnow?token=5O190127TN364715T"},
        ],
    })
    order = paypal.create_order(PRODUCT, "http://app", "http://app/?cancelled=true")
    assert order["approve_url"].endswith("token=5O190127TN364715T")
    assert calls[1][1]["headers"]["Authorization"] == "Bearer token-123"


def test_capture_order_is_idempotent_and_summarized(fake_paypal):
    calls, responses = fake_paypal
    responses["checkout/orders/5O190127TN364715T/capture"] = FakeResponse(201, {
        "id": "5O190127TN364715T",
        "status": "COMPLETED",
        "payer": {"name": {"given_name": "Sam", "surname": "Buyer"}, "email_address": "sam@example.com"},
        "purchase_units": [{
            "reference_id": "HP-02",
            "payments": {"captures": [{
                "id": "3C679366HH908993F",
                "status": "COMPLETED",
                "amount": {"currency_code": "USD", "value": "149.00"},
            }]},
        }],
    })
    receipt = paypal.capture_order("5O190127TN364715T")
    assert receipt == {
        "order_id": "5O190127TN364715T",
        "status": "COMPLETED",
        "capture_id": "3C679366HH908993F",
        "capture_status": "COMPLETED",
        "amount": "149.00",
        "currency": "USD",
        "product_id": "HP-02",
        "payer_name": "Sam Buyer",
        "payer_email": "sam@example.com",
    }
    assert calls[1][1]["headers"]["PayPal-Request-Id"] == "consensuscart-capture-5O190127TN364715T"


def test_capture_rejects_malformed_order_ids(fake_paypal):
    with pytest.raises(paypal.PayPalError, match="Invalid PayPal order ID"):
        paypal.capture_order("../../v1/oauth2")


def test_api_errors_raise_paypal_error(fake_paypal):
    _, responses = fake_paypal
    responses["checkout/orders/5O190127TN364715T/capture"] = FakeResponse(422, {
        "name": "UNPROCESSABLE_ENTITY",
        "message": "The requested action could not be performed.",
        "details": [{"issue": "ORDER_NOT_APPROVED"}],
    })
    with pytest.raises(paypal.PayPalError, match="ORDER_NOT_APPROVED"):
        paypal.capture_order("5O190127TN364715T")


def test_missing_credentials_raise_clear_error(monkeypatch):
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    assert not paypal.is_configured()
    with pytest.raises(paypal.PayPalError, match="PAYPAL_CLIENT_ID"):
        paypal.get_access_token()
