from langchain_core.prompts import ChatPromptTemplate

from agents.common import format_products, get_model, validate_recommendation
from agents.schema import ProductRecommendation

trust_agent_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Trust Agent for ConsensusCart.

Evaluate products using only the evidence in the product data:
- Seller reputation, only when supported by actual data (e.g. a seller rating field)
- Return and refund policies
- Warranty information
- Product review evidence (ratings, review counts)
- Missing or contradictory product information

Only recommend products from the catalog, using their exact product_id.
Never invent seller ratings, reviews, policies, or reliability claims.
If information is missing, say so explicitly and treat it as a trade-off.
Lower your confidence when the evidence is thin.
List each trade-off as a separate item."""
    ),
    (
        "human",
        """Shopping request: {query}

Available products:
{product_details}"""
    ),
])


def get_trust_chain():
    return trust_agent_prompt | get_model().with_structured_output(ProductRecommendation)


def run_trust_agent(state):
    products = state["eligible_products"]
    recommendation = get_trust_chain().invoke({
        "query": state["query"],
        "product_details": format_products(products),
    })
    return {"trust_recommendation": validate_recommendation(recommendation, products)}
