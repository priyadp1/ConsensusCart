from langgraph.graph import END, START, StateGraph
from agents.budget_agent import run_budget_agent
from agents.quality_agent import run_quality_agent
from agents.state import ConsensusState
from agents.trust_agent import run_trust_agent
from consensus.aggregation import AGENTS, aggregate, finalize
from consensus.deliberation import make_deliberation_node, route_after_aggregate


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

graph.add_node("aggregate", aggregate)
graph.add_node("finalize", finalize)
for agent in AGENTS:
    graph.add_node(f"deliberate_{agent}", make_deliberation_node(agent))

graph.add_edge(START, "filter_budget")

# Round 0: independent evaluations in parallel, then aggregate once all three finish
for agent in AGENTS:
    graph.add_edge("filter_budget", agent)
graph.add_edge(list(AGENTS), "aggregate")

# Deliberation loop: aggregate -> (all three agents reconsider) -> aggregate ... -> finalize
deliberation_nodes = [f"deliberate_{agent}" for agent in AGENTS]
graph.add_conditional_edges("aggregate", route_after_aggregate, deliberation_nodes + ["finalize"])
graph.add_edge(deliberation_nodes, "aggregate")
graph.add_edge("finalize", END)

consensus_graph = graph.compile()
