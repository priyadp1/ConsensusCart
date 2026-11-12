from langchain_core.prompts import ChatPromptTemplate
from agents.common import format_products, get_model, validate_recommendation
from agents.schema import ProductRecommendation
from data.catalog import with_offers

DEALS_SYSTEM_PROMPT = """You are the Deals Agent for ConsensusCart.

Evaluate products using the seller offers listed for each product:
- Prices across sellers, and how much the best offer saves versus the catalog price
- Discounts, judged by the money they actually save, not the percentage alone
- Shipping costs and delivery times
- Total cost (sale price plus shipping), which is already calculated; offers are sorted by it
- Offer condition (new or refurbished) and the rating of the seller making the offer

Every product you are given is already within the budget.
Only recommend products from the catalog, using their exact product_id.
Never invent prices, discounts, coupons or shipping costs, and do not recalculate the totals.
A total_cost of null means shipping is not stated: treat that total as unknown, not as free shipping.
Sales tax is not included in any total.
List each trade-off as a separate item."""

deals_agent_prompt = ChatPromptTemplate.from_messages([
    ("system", DEALS_SYSTEM_PROMPT),
    (
        "human",
        """Shopping request: {query}

Maximum budget: ${budget}

Available products and seller offers:
{product_details}"""
    ),
])


def get_deals_chain():
    return deals_agent_prompt | get_model().with_structured_output(ProductRecommendation)


def run_deals_agent(state):
    products = state["eligible_products"]
    recommendation = get_deals_chain().invoke({
        "query": state["query"],
        "budget": state["budget"],
        "product_details": format_products(with_offers(products)),
    })
    return {"deals_recommendation": validate_recommendation(recommendation, products)}
