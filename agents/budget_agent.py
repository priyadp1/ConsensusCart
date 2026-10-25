from langchain_core.prompts import ChatPromptTemplate

from agents.common import format_products, get_model, validate_recommendation
from agents.schema import ProductRecommendation

budget_agent_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Budget Agent for ConsensusCart.

Evaluate products based on:
- Price relative to the user's budget
- Value for money (what the user gets for the price)
- Hidden or ongoing costs, when stated in the product data

Every product you are given is already within the budget.
Only recommend products from the catalog, using their exact product_id.
Do not invent prices, discounts, or specifications.
List each trade-off as a separate item."""
    ),
    (
        "human",
        """Shopping request: {query}

Maximum budget: ${budget}

Available products:
{product_details}"""
    ),
])


def get_budget_chain():
    return budget_agent_prompt | get_model().with_structured_output(ProductRecommendation)


def run_budget_agent(state):
    products = state["eligible_products"]
    recommendation = get_budget_chain().invoke({
        "query": state["query"],
        "budget": state["budget"],
        "product_details": format_products(products),
    })
    return {"budget_recommendation": validate_recommendation(recommendation, products)}
