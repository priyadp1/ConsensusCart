from typing import TypedDict


class ConsensusState(TypedDict, total=False):
    # Inputs
    query: str
    budget: float
    preferences: str
    products: list[dict]

    # Set by the budget filter: products with price <= budget
    eligible_products: list[dict]

    # Round 0: each agent writes its own key, so the nodes can run in parallel
    budget_recommendation: dict
    quality_recommendation: dict
    trust_recommendation: dict
