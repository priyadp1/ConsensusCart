import pytest
from langchain_core.runnables import RunnableLambda
import agents.budget_agent as budget_agent
import agents.deals_agent as deals_agent
import agents.quality_agent as quality_agent
import agents.trust_agent as trust_agent
from agents.orchestrator import consensus_graph, filter_by_budget
import consensus.deliberation as deliberation
from agents.schema import DeliberationResponse

PRODUCTS = [
    {"product_id": "A", "name": "Premium Headphones", "price": 299.0},
    {"product_id": "B", "name": "Budget Headphones", "price": 149.0},
    {"product_id": "C", "name": "Mid-range Headphones", "price": 199.0},
]


class FakeModel:
    def __init__(self, product_id="B"):
        self.product_id = product_id
        self.prompts = []

    def with_structured_output(self, schema):
        def respond(prompt):
            self.prompts.append(prompt.to_string())
            fields = {
                "product_id": self.product_id,
                "confidence": 0.8,
                "reasoning": "Fits the request.",
                "tradeoffs": ["Shorter warranty", "Fewer reviews"],
            }
            # Deliberation nodes ask for DeliberationResponse, which needs an extra field
            if issubclass(schema, DeliberationResponse):
                fields["response_to_others"] = "Considered the other agents."
            return schema(**fields)

        return RunnableLambda(respond)


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeModel()
    for module in (budget_agent, quality_agent, trust_agent, deals_agent, deliberation):
        monkeypatch.setattr(module, "get_model", lambda: model)
    return model


def make_state(**overrides):
    state = {
        "query": "wireless headphones",
        "budget": 200,
        "preferences": "battery life over sound quality",
        "products": PRODUCTS,
    }
    state.update(overrides)
    return state


def test_filter_by_budget_removes_unaffordable_products():
    result = filter_by_budget(make_state())
    assert [p["product_id"] for p in result["eligible_products"]] == ["B", "C"]


def test_filter_by_budget_raises_when_nothing_affordable():
    with pytest.raises(ValueError, match="No products within budget"):
        filter_by_budget(make_state(budget=50))


def test_graph_returns_all_four_recommendations(fake_model):
    result = consensus_graph.invoke(make_state())

    for key in ("budget_recommendation", "quality_recommendation", "trust_recommendation", "deals_recommendation"):
        recommendation = result[key]
        assert recommendation["product_id"] == "B"
        assert 0 <= recommendation["confidence"] <= 1
        assert isinstance(recommendation["tradeoffs"], list)


def test_agents_never_see_over_budget_products(fake_model):
    consensus_graph.invoke(make_state())

    assert len(fake_model.prompts) == 4
    for prompt in fake_model.prompts:
        assert "Premium Headphones" not in prompt
        assert "Budget Headphones" in prompt


def test_quality_agent_receives_preferences(fake_model):
    quality_agent.run_quality_agent(make_state(eligible_products=PRODUCTS[1:]))
    assert "battery life over sound quality" in fake_model.prompts[0]


def test_quality_agent_handles_missing_preferences(fake_model):
    state = make_state(eligible_products=PRODUCTS[1:])
    del state["preferences"]
    quality_agent.run_quality_agent(state)
    assert "None stated" in fake_model.prompts[0]


@pytest.mark.parametrize("run_agent", [
    budget_agent.run_budget_agent,
    quality_agent.run_quality_agent,
    trust_agent.run_trust_agent,
    deals_agent.run_deals_agent,
])
def test_agents_reject_unknown_product_ids(monkeypatch, run_agent):
    model = FakeModel(product_id="Z")
    for module in (budget_agent, quality_agent, trust_agent, deals_agent):
        monkeypatch.setattr(module, "get_model", lambda: model)

    with pytest.raises(ValueError, match="Unknown product ID"):
        run_agent(make_state(eligible_products=PRODUCTS[1:]))


def test_agents_reject_over_budget_product_ids(monkeypatch):
    model = FakeModel(product_id="A")
    monkeypatch.setattr(budget_agent, "get_model", lambda: model)

    with pytest.raises(ValueError, match="Unknown product ID"):
        budget_agent.run_budget_agent(make_state(eligible_products=PRODUCTS[1:]))


def test_deals_agent_sees_seller_offers_and_totals(fake_model):
    from data.catalog import load_products
    products = load_products("Headphones")
    fake_model.product_id = "HP-04"
    deals_agent.run_deals_agent(make_state(eligible_products=products))
    prompt = fake_model.prompts[0]
    assert "You are the Deals Agent" in prompt
    assert "MegaMart Online" in prompt          # a seller that only appears in offers.csv
    assert "179.55" in prompt                   # precomputed total, not left to the model
