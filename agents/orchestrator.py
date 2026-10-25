from langgraph.graph import END, START, StateGraph

from agents.budget_agent import run_budget_agent
from agents.quality_agent import run_quality_agent
from agents.state import ConsensusState
from agents.trust_agent import run_trust_agent


def filter_by_budget(state):
    eligible_products = [
        product for product in state["products"]
        if float(product["price"]) <= state["budget"]
    ]
    if not eligible_products:
        raise ValueError(f"No products within budget of ${state['budget']}")
    return {"eligible_products": eligible_products}


graph = StateGraph(ConsensusState)

graph.add_node("filter_budget", filter_by_budget)
graph.add_node("budget", run_budget_agent)
graph.add_node("quality", run_quality_agent)
graph.add_node("trust", run_trust_agent)

graph.add_edge(START, "filter_budget")


# TODO: replace the END edges with an aggregation node + deliberation loop.
for agent in ("budget", "quality", "trust"):
    graph.add_edge("filter_budget", agent)
    graph.add_edge(agent, END)

consensus_graph = graph.compile()
