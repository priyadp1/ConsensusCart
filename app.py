import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def load_streamlit_secrets():
    """On Streamlit Cloud the keys live in st.secrets; copy them into the environment the agents read."""
    try:
        secrets = dict(st.secrets)
    except Exception:  # no secrets.toml locally
        return
    for key, value in secrets.items():
        values = dict(value) if hasattr(value, "items") else {key: value}  # also accept a [section] table
        for name, setting in values.items():
            if isinstance(setting, str) and setting.strip() and not os.getenv(name):
                os.environ[name] = setting.strip()


load_streamlit_secrets()

from agents.orchestrator import consensus_graph  # noqa: E402  (needs the .env loaded first)
from data.catalog import categories, get_product, load_offers, load_products  # noqa: E402
from payments import paypal  # noqa: E402

APP_URL = os.getenv("APP_URL", "http://localhost:8501").rstrip("/")

AGENT_LABELS = {
    "budget": "💰 Budget Agent",
    "quality": "⭐ Quality Agent",
    "trust": "🛡️ Trust Agent",
    "deals": "🏷️ Deals Agent",
}

EXAMPLE_QUERIES = {
    "Headphones": "Noise cancelling headphones for my daily train commute",
    "Laptops": "A light laptop for college with all-day battery",
    "Coffee Makers": "Something that makes great coffee every morning without fuss",
}

st.set_page_config(page_title="ConsensusCart", page_icon="🛒", layout="wide")


def product_label(product_id, products):
    product = next((p for p in products if p["product_id"] == product_id), None)
    return f"{product['name']} (${product['price']:.2f})" if product else product_id


def describe_update(node, update):
    """One progress line per graph node, shown while the agents work."""
    if node == "filter_budget":
        return f"🔎 {len(update['eligible_products'])} products are within budget"
    if node in AGENT_LABELS:
        return f"{AGENT_LABELS[node]} made its independent pick"
    if node.startswith("deliberate_"):
        return f"{AGENT_LABELS[node.removeprefix('deliberate_')]} reconsidered its pick"
    if node == "aggregate":
        latest = update["rounds"][-1]
        stage = "Independent round" if latest["round"] == 0 else f"Deliberation round {latest['round']}"
        return f"🗳️ {stage}: {latest['agreement']:.0%} agreement"
    if node == "finalize":
        return "✅ Consensus finalized"
    return None


def money(value, missing="Not stated"):
    return missing if value is None else f"${value:,.2f}"


def render_offers(product):
    offers = load_offers(product["product_id"])
    if not offers:
        return
    st.markdown("**🏷️ Prices across sellers**")
    rows = [
        {
            "Seller": offer["seller"],
            "Seller rating": offer["seller_rating"],
            "Condition": offer["condition"],
            "Price": money(offer["price"]),
            "Discount": f"{offer['discount_percent']:.0f}%" if offer["discount_percent"] else "—",
            "Sale price": money(offer["sale_price"]),
            "Shipping": "Free" if offer["shipping_cost"] == 0 else money(offer["shipping_cost"]),
            "Delivery": f"{offer['delivery_days']} days" if offer["delivery_days"] else "Not stated",
            "Total cost": money(offer["total_cost"], missing="Unknown"),
        }
        for offer in offers
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption(
        f"Totals exclude sales tax. Checkout below is with {product['seller']} at ${product['price']:.2f}."
    )


def run_consensus(state):
    result = None
    with st.status("Agents are evaluating products…", expanded=True) as status:
        for mode, chunk in consensus_graph.stream(state, stream_mode=["updates", "values"]):
            if mode == "values":
                result = chunk
                continue
            for node, update in chunk.items():
                message = describe_update(node, update or {})
                if message:
                    status.write(message)
        status.update(label="Agents reached a decision", state="complete", expanded=False)
    return result


def handle_paypal_return():
    """PayPal sends the buyer back to APP_URL with ?token=<order ID> after approving or cancelling."""
    params = st.query_params
    order_id = params.get("token")
    if not order_id:
        return
    if params.get("cancelled"):
        st.session_state["checkout_notice"] = ("warning", "Checkout was cancelled. No payment was taken.")
    elif st.session_state.get("receipt", {}).get("order_id") != order_id:
        try:
            with st.spinner("Completing your PayPal payment…"):
                st.session_state["receipt"] = paypal.capture_order(order_id)
        except (paypal.PayPalError, OSError) as error:
            st.session_state["checkout_notice"] = ("error", f"Payment could not be completed: {error}")
    st.query_params.clear()


def render_receipt(receipt):
    product = get_product(receipt["product_id"]) if receipt.get("product_id") else None
    if receipt.get("capture_status") == "COMPLETED":
        st.success("🎉 Payment complete! Your order has been placed.")
        st.balloons()
    else:
        st.warning(f"Payment status: {receipt.get('capture_status') or receipt.get('status')}")
    cols = st.columns(3)
    cols[0].metric("Product", product["name"] if product else receipt.get("product_id") or "—")
    cols[1].metric("Amount paid", f"{receipt.get('amount')} {receipt.get('currency') or ''}".strip())
    cols[2].metric("PayPal order", receipt["order_id"])
    details = {"Capture ID": receipt.get("capture_id"), "Payer": receipt.get("payer_name"),
               "Payer email": receipt.get("payer_email")}
    st.caption(" · ".join(f"{k}: {v}" for k, v in details.items() if v))
    if st.button("Start a new search"):
        for key in ("receipt", "result", "order", "choice"):
            st.session_state.pop(key, None)
        st.rerun()


def render_consensus(result):
    consensus = result["consensus"]
    product = consensus["product"]
    products = result["eligible_products"]

    st.subheader("🏆 Consensus Pick")
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            st.markdown(f"### {product['name']}")
            st.markdown(f"**${product['price']:.2f}** · {product['brand']} · sold by {product['seller']}")
            st.write(product.get("description") or "")
            st.markdown("\n".join(f"- {feature}" for feature in product["features"]))
        with right:
            supporters = ", ".join(AGENT_LABELS[a] for a in consensus["supporters"])
            verdict = "Unanimous" if consensus["unanimous"] else "Majority" if consensus["agreement"] > 0.5 else "Split"
            st.metric("Agreement", f"{consensus['agreement']:.0%}", verdict, delta_color="off")
            st.progress(consensus["agreement"], text=f"Backed by {supporters}")
            st.caption(
                f"⭐ {product.get('rating') or '—'} ({product.get('review_count') or 0} reviews) · "
                f"Warranty: {product.get('warranty_months') or 'not stated'} mo · "
                f"Returns: {product.get('return_window_days') or 'not stated'} days"
            )
        for dissent in consensus["dissent"]:
            st.warning(
                f"**{AGENT_LABELS[dissent['agent']]} dissents** and still prefers "
                f"{product_label(dissent['product_id'], products)}: {dissent['reasoning']}"
            )
        render_offers(product)

    st.subheader("🤖 Agent Recommendations")
    first_round = result["rounds"][0]["recommendations"]
    for agent, column in zip(AGENT_LABELS, st.columns(len(AGENT_LABELS))):
        recommendation = result[f"{agent}_recommendation"]
        with column, st.container(border=True):
            st.markdown(f"**{AGENT_LABELS[agent]}**")
            st.markdown(f"Picks **{product_label(recommendation['product_id'], products)}**")
            initial = first_round[agent]["product_id"]
            if initial != recommendation["product_id"]:
                st.caption(f"🔄 Changed its mind (first picked {product_label(initial, products)})")
            st.progress(recommendation["confidence"], text=f"Confidence {recommendation['confidence']:.0%}")
            st.write(recommendation["reasoning"])
            if recommendation["tradeoffs"]:
                st.markdown("**Trade-offs**\n" + "\n".join(f"- {t}" for t in recommendation["tradeoffs"]))
            if recommendation.get("response_to_others"):
                with st.expander("Response to the other agents"):
                    st.write(recommendation["response_to_others"])

    st.subheader("🗳️ Deliberation")
    rows = [
        {
            "Round": "Independent" if r["round"] == 0 else f"Deliberation {r['round']}",
            **{AGENT_LABELS[a]: product_label(rec["product_id"], products) for a, rec in r["recommendations"].items()},
            "Agreement": f"{r['agreement']:.0%}",
            "Changed": ", ".join(r["changed"]) or "—",
        }
        for r in result["rounds"]
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    if consensus["deliberation_rounds"] == 0:
        st.caption("All agents agreed independently, so no deliberation was needed.")
    elif not consensus["unanimous"]:
        st.caption("The agents hit the deliberation round limit without full agreement; the majority pick wins.")


def choose_product(result):
    """The consensus is a recommendation: the buyer can pick any other product the agents considered."""
    consensus = result["consensus"]
    products = result["eligible_products"]
    product_ids = [p["product_id"] for p in products]

    st.subheader("🛍️ Your Choice")
    choice = st.selectbox(
        "Buy the consensus pick, or override it with another product within your budget",
        product_ids,
        index=product_ids.index(consensus["product_id"]),
        format_func=lambda pid: ("🏆 " if pid == consensus["product_id"] else "") + product_label(pid, products),
        key="choice",
    )
    product = next(p for p in products if p["product_id"] == choice)
    if choice == consensus["product_id"]:
        return product

    backers = [AGENT_LABELS[a] for a in AGENT_LABELS if result[f"{a}_recommendation"]["product_id"] == choice]
    support = f"Backed by {', '.join(backers)}." if backers else "None of the agents picked this product."
    st.info(
        f"**You're overriding the agents' consensus** ({product_label(consensus['product_id'], products)}) "
        f"with **{product['name']}**, ${product['price']:.2f} from {product['seller']}. {support}"
    )
    render_offers(product)
    return product


def render_checkout(product):
    st.subheader("💳 Checkout")
    if not paypal.is_configured():
        st.info("PayPal checkout is disabled. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (Sandbox) to enable it.")
        return
    order = st.session_state.get("order")
    if order and order["product_id"] == product["product_id"]:
        st.link_button("Approve payment on PayPal →", order["approve_url"], type="primary")
        st.caption(f"PayPal Sandbox order {order['id']} created. Log in with a sandbox buyer account to pay.")
        return
    if st.button(f"Buy with PayPal — ${product['price']:.2f}", type="primary"):
        try:
            with st.spinner("Creating PayPal order…"):
                order = paypal.create_order(
                    product,
                    return_url=APP_URL,
                    cancel_url=f"{APP_URL}/?cancelled=true",
                )
        except (paypal.PayPalError, OSError) as error:
            st.error(f"Could not start checkout: {error}")
            return
        st.session_state["order"] = {**order, "product_id": product["product_id"]}
        st.rerun()


st.title("🛒 ConsensusCart")
st.caption("Four AI shopping agents debate until they agree, then you check out with PayPal.")

handle_paypal_return()
if notice := st.session_state.pop("checkout_notice", None):
    getattr(st, notice[0])(notice[1])
if "receipt" in st.session_state:
    render_receipt(st.session_state["receipt"])
    st.stop()

# Not an st.form: every edit reruns the page, so results from an older search can be hidden right away
category = st.selectbox("Category", categories())
query = st.text_input("What are you shopping for?", placeholder=EXAMPLE_QUERIES.get(category, ""))
left, right = st.columns(2)
budget = left.number_input("Maximum budget ($)", min_value=1, value=200, step=10)
preferences = right.text_input("Preferences (optional)", placeholder="e.g. battery life over sound quality")
submitted = st.button("Find Best Products", type="primary")

search = {
    "category": category,
    "query": query.strip() or EXAMPLE_QUERIES.get(category, category),
    "budget": float(budget),
    "preferences": preferences.strip(),
}

if submitted:
    for key in ("order", "choice"):  # a new search starts from the new consensus pick
        st.session_state.pop(key, None)
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not set. Add it to your environment or a .env file.")
        st.stop()
    state = {
        "query": search["query"],
        "budget": search["budget"],
        "preferences": search["preferences"],
        "products": load_products(category),
    }
    try:
        st.session_state["result"] = {**run_consensus(state), "search": search}
    except ValueError as error:
        st.session_state.pop("result", None)
        st.error(str(error))
    except Exception as error:  # LLM/network failures should not crash the demo
        st.session_state.pop("result", None)
        st.error(f"The agents could not finish: {error}")

result = st.session_state.get("result")
if result and result["search"] != search:
    st.info("Your search changed. Click **Find Best Products** to get new recommendations.")
elif result:
    st.caption(f"Results for “{search['query']}” in {search['category']}, up to ${search['budget']:,.0f}")
    render_consensus(result)
    render_checkout(choose_product(result))
