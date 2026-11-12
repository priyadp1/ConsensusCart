from consensus.metrics import (
    calculate_agreement,
    changed_agents,
    confidence_by_product,
    count_votes,
    is_unanimous,
)

AGENTS = ("budget", "quality", "trust")


def collect_recommendations(state):
    return {agent: state[f"{agent}_recommendation"] for agent in AGENTS}


def aggregate(state):
    """Record the round that just finished, so the router and the UI can see how opinions moved."""
    recommendations = collect_recommendations(state)
    previous_rounds = state.get("rounds", [])
    previous = previous_rounds[-1]["recommendations"] if previous_rounds else {}

    return {"rounds": [{
        "round": len(previous_rounds),
        "recommendations": recommendations,
        "votes": dict(count_votes(recommendations)),
        "agreement": calculate_agreement(recommendations),
        "unanimous": is_unanimous(recommendations),
        "changed": changed_agents(previous, recommendations),
    }]}


def select_winner(recommendations):
    """Most votes wins; a tie (e.g. a three-way split) goes to the highest total confidence."""
    votes = count_votes(recommendations)
    confidence = confidence_by_product(recommendations)
    return max(votes, key=lambda product_id: (votes[product_id], confidence[product_id]))


def finalize(state):
    final_round = state["rounds"][-1]
    recommendations = final_round["recommendations"]
    winner = select_winner(recommendations)

    product = next(
        (p for p in state["eligible_products"] if str(p["product_id"]) == winner),
        None,
    )
    if product is None:
        raise ValueError(f"Consensus product {winner} is not in the eligible catalog")

    return {"consensus": {
        "product_id": winner,
        "product": product,
        "agreement": final_round["agreement"],
        "unanimous": final_round["unanimous"],
        "deliberation_rounds": final_round["round"],
        "agreement_by_round": [r["agreement"] for r in state["rounds"]],
        "supporters": [a for a, rec in recommendations.items() if rec["product_id"] == winner],
        "dissent": [
            {"agent": a, "product_id": rec["product_id"], "reasoning": rec["reasoning"]}
            for a, rec in recommendations.items()
            if rec["product_id"] != winner
        ],
    }}
