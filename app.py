import app as st

st.set_page_config(
    page_title="ConsensusCart",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 ConsensusCart")
st.caption("Multi-Agent AI Shopping Assistant")

query = st.text_input(
    "What are you shopping for?",
    placeholder="Best headphones under $200"
)

budget = st.number_input(
    "Maximum budget ($)",
    min_value=1,
    value=200
)

if st.button("Find Best Products", type="primary"):
    st.session_state["query"] = query
    st.session_state["budget"] = budget

if "query" in st.session_state:
    st.subheader("AI Agent Recommendations")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("💰 Budget Agent")
        st.write("Evaluates price and value.")

    with col2:
        st.info("⭐ Quality Agent")
        st.write("Evaluates features and performance.")

    with col3:
        st.info("🛡️ Trust Agent")
        st.write("Evaluates merchant reliability.")

    st.subheader("Consensus Analysis")
    st.progress(0.67, text="Illustrative: 2 of 3 agents agree")

    st.subheader("Recommended Product")
    st.write("Product A — $179.99 (example)")

    if st.button("Proceed to PayPal Checkout"):
        st.warning("Connect PayPal Sandbox Orders API here.")
