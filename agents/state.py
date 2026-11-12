import operator
from typing import Annotated, TypedDict


class ConsensusState(TypedDict, total=False):
    # Inputs
    query: str
    budget: float
    preferences: str
    products: list[dict]

    # Set by the budget filter: products with price <= budget
    eligible_products: list[dict]

    # Each agent writes its own key, so the nodes can run in parallel.
    # Round 0 sets them; every deliberation round overwrites them.
    budget_recommendation: dict
    quality_recommendation: dict
    trust_recommendation: dict
    deals_recommendation: dict

    # One entry per round, appended by the aggregate node (round 0 = independent)
    rounds: Annotated[list[dict], operator.add]

    # Set by the finalize node
    consensus: dict
