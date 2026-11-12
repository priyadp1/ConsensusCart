import json
from langchain_core.prompts import ChatPromptTemplate
from agents.budget_agent import BUDGET_SYSTEM_PROMPT
from agents.common import format_products, get_model, validate_recommendation
from agents.quality_agent import QUALITY_SYSTEM_PROMPT
from agents.schema import DeliberationResponse
from agents.trust_agent import TRUST_SYSTEM_PROMPT
from consensus.aggregation import AGENTS, collect_recommendations

MAX_DELIBERATION_ROUNDS = 2

SYSTEM_PROMPTS = {
    "budget": BUDGET_SYSTEM_PROMPT,
    "quality": QUALITY_SYSTEM_PROMPT,
    "trust": TRUST_SYSTEM_PROMPT,
}

DELIBERATION_INSTRUCTIONS = """

You are now in deliberation round {round}. The other ConsensusCart agents have
different priorities, and their recommendations are shown below alongside yours.

Re-examine the product data and decide whether to keep or change your recommendation:
- Keep your recommendation if your reasoning still holds. Do not switch just because you are outvoted.
- Switch only if another agent raised evidence from the product data that outweighs your own priorities.
- Check the other agents' claims against the product data and point out any claim it does not support.
- Adjust your confidence to reflect how strong the remaining disagreement is.
In response_to_others, say which arguments did or did not change your mind, and why."""


def get_deliberation_chain(agent):
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPTS[agent] + DELIBERATION_INSTRUCTIONS),
        (
            "human",
            """Shopping request: {query}

Maximum budget: ${budget}

User preferences: {preferences}

Available products:
{product_details}

Your previous recommendation:
{own_recommendation}

The other agents' recommendations:
{other_recommendations}"""
        ),
    ])
    return prompt | get_model().with_structured_output(DeliberationResponse)


def make_deliberation_node(agent):
    def deliberate(state):
        products = state["eligible_products"]
        recommendations = collect_recommendations(state)
        others = {name: rec for name, rec in recommendations.items() if name != agent}

        response = get_deliberation_chain(agent).invoke({
            "round": len(state["rounds"]),
            "query": state["query"],
            "budget": state["budget"],
            "preferences": state.get("preferences") or "None stated",
            "product_details": format_products(products),
            "own_recommendation": json.dumps(recommendations[agent], indent=2),
            "other_recommendations": json.dumps(others, indent=2),
        })
        return {f"{agent}_recommendation": validate_recommendation(response, products)}

    return deliberate


def route_after_aggregate(state):
    latest = state["rounds"][-1]
    if latest["unanimous"] or latest["round"] >= MAX_DELIBERATION_ROUNDS:
        return "finalize"
    return [f"deliberate_{agent}" for agent in AGENTS]
