"""Minimal PayPal Orders v2 client: create an order, send the buyer to approve it, then capture it."""
import os
import re
import requests

SANDBOX_URL = "https://api-m.sandbox.paypal.com"
TIMEOUT = 20
ORDER_ID_PATTERN = re.compile(r"[A-Z0-9]{5,40}")


class PayPalError(RuntimeError):
    pass


def base_url():
    return os.getenv("PAYPAL_BASE_URL", SANDBOX_URL).rstrip("/")


def is_configured():
    return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))


def _check(response):
    if response.ok:
        return response.json()
    try:
        error = response.json()
    except ValueError:
        error = {}
    issue = (error.get("details") or [{}])[0].get("issue")
    message = error.get("message") or error.get("error_description") or response.text[:200]
    raise PayPalError(
        f"PayPal {response.status_code}: {issue or error.get('name') or error.get('error', '')} {message}".strip()
    )


def get_access_token():
    if not is_configured():
        raise PayPalError("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to enable checkout.")
    response = requests.post(
        f"{base_url()}/v1/oauth2/token",
        auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    return _check(response)["access_token"]


def _headers(**extra):
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        **extra,
    }


def build_order_request(product, return_url, cancel_url, currency="USD"):
    return {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": product["product_id"],
            "description": product["name"][:127],
            "amount": {"currency_code": currency, "value": f"{float(product['price']):.2f}"},
        }],
        "payment_source": {"paypal": {"experience_context": {
            "brand_name": "ConsensusCart",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        }}},
    }


def create_order(product, return_url, cancel_url):
    """Create an order for one catalog product; returns its ID and the URL where the buyer approves it."""
    response = requests.post(
        f"{base_url()}/v2/checkout/orders",
        json=build_order_request(product, return_url, cancel_url),
        headers=_headers(),
        timeout=TIMEOUT,
    )
    order = _check(response)
    approve_url = next(
        (link["href"] for link in order.get("links", []) if link["rel"] in ("payer-action", "approve")),
        None,
    )
    if approve_url is None:
        raise PayPalError(f"PayPal order {order.get('id')} has no approval link")
    return {"id": order["id"], "status": order["status"], "approve_url": approve_url}


def validate_order_id(order_id):
    # The order ID comes back in the return URL, so check it before putting it in an API path
    if not ORDER_ID_PATTERN.fullmatch(order_id or ""):
        raise PayPalError(f"Invalid PayPal order ID: {order_id!r}")
    return order_id


def capture_order(order_id):
    """Capture an approved order. The request ID makes retries (e.g. a page refresh) idempotent."""
    order_id = validate_order_id(order_id)
    response = requests.post(
        f"{base_url()}/v2/checkout/orders/{order_id}/capture",
        headers=_headers(**{"PayPal-Request-Id": f"consensuscart-capture-{order_id}"}),
        timeout=TIMEOUT,
    )
    return summarize_capture(_check(response))


def summarize_capture(order):
    unit = (order.get("purchase_units") or [{}])[0]
    capture = ((unit.get("payments") or {}).get("captures") or [{}])[0]
    payer = order.get("payer") or {}
    name = payer.get("name") or {}
    return {
        "order_id": order.get("id"),
        "status": order.get("status"),
        "capture_id": capture.get("id"),
        "capture_status": capture.get("status"),
        "amount": (capture.get("amount") or {}).get("value"),
        "currency": (capture.get("amount") or {}).get("currency_code"),
        "product_id": unit.get("reference_id"),
        "payer_name": " ".join(filter(None, (name.get("given_name"), name.get("surname")))) or None,
        "payer_email": payer.get("email_address"),
    }
