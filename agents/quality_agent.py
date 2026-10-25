from langchain_core.prompts import ChatPromptTemplate

from agents.common import format_products, get_model, validate_recommendation
from agents.schema import ProductRecommendation

quality_agent_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Quality Agent for ConsensusCart.

Evaluate products based on:
- Product specifications
- Feature quality
- User preferences
- Overall suitability

Only recommend products from the catalog, using their exact product_id.
Do not invent specifications.
Explain the strengths and list each trade-off as a separate item."""
    ),
    (
        "human",
        """Shopping request: {query}

User preferences: {preferences}

Available products:
{product_details}"""
    ),
])


def get_quality_chain():
    return quality_agent_prompt | get_model().with_structured_output(ProductRecommendation)


def run_quality_agent(state):
    products = state["eligible_products"]
    recommendation = get_quality_chain().invoke({
        "query": state["query"],
        "preferences": state.get("preferences") or "None stated",
        "product_details": format_products(products),
    })
    return {"quality_recommendation": validate_recommendation(recommendation, products)}
