import pytest
from langchain_core.runnables import RunnableLambda
import agents.budget_agent as budget_agent
import agents.deals_agent as deals_agent
import agents.quality_agent as quality_agent
import agents.trust_agent as trust_agent
import consensus.deliberation as deliberation
from agents.orchestrator import consensus_graph
from agents.schema import DeliberationResponse
from consensus.aggregation import AGENTS, finalize, select_winner
from consensus.metrics import calculate_agreement, changed_agents
from tests.test_agents import make_state


class ScriptedModel:
    """Each agent answers from its own script: one product ID per round, repeating the last one."""

    def __init__(self, script, confidence=None):
        self.script = script
        self.confidence = confidence or {}
        self.prompts = {agent: [] for agent in script}

    def with_structured_output(self, schema):
        def respond(prompt):
            text = prompt.to_string()
            agent = next(a for a in self.script if f"You are the {a.title()} Agent" in text)
            self.prompts[agent].append(text)
            choices = self.script[agent]
            fields = {
                "product_id": choices[min(len(self.prompts[agent]), len(choices)) - 1],
                "confidence": self.confidence.get(agent, 0.8),
                "reasoning": f"{agent} reasoning",
                "tradeoffs": ["Some trade-off"],
            }
            if schema is DeliberationResponse:
                fields["response_to_others"] = "Considered the other agents."
            return schema(**fields)

        return RunnableLambda(respond)

    def deliberation_prompts(self):
        return [p for prompts in self.prompts.values() for p in prompts if "deliberation round" in p]


@pytest.fixture
def scripted(monkeypatch):
    def install(script, confidence=None):
        model = ScriptedModel(script, confidence)
        for module in (budget_agent, quality_agent, trust_agent, deals_agent, deliberation):
            monkeypatch.setattr(module, "get_model", lambda: model)
        return model

    return install


def recs(*product_ids):
    return {
        agent: {"product_id": pid, "confidence": 0.8, "reasoning": "", "tradeoffs": []}
        for agent, pid in zip(AGENTS, product_ids)
    }


@pytest.mark.parametrize("product_ids, expected", [
    (("A", "A", "A", "A"), 1.0),
    (("A", "A", "A", "B"), 3 / 4),
    (("A", "A", "B", "C"), 1 / 2),
    (("A", "B", "C", "D"), 1 / 4),
])
def test_calculate_agreement(product_ids, expected):
    assert calculate_agreement(recs(*product_ids)) == pytest.approx(expected)


def test_changed_agents():
    assert changed_agents(recs("B", "C", "B", "B"), recs("B", "B", "B", "B")) == ["quality"]
    assert changed_agents({}, recs("B", "B", "B", "B")) == []


def test_select_winner_breaks_four_way_tie_by_confidence():
    recommendations = recs("A", "B", "C", "D")
    recommendations["trust"]["confidence"] = 0.95
    assert select_winner(recommendations) == "C"


def test_select_winner_breaks_two_two_split_by_confidence():
    recommendations = recs("A", "A", "B", "B")
    recommendations["deals"]["confidence"] = 0.95
    assert select_winner(recommendations) == "B"


def test_unanimous_round_zero_skips_deliberation(scripted):
    model = scripted({"budget": ["B"], "quality": ["B"], "trust": ["B"], "deals": ["B"]})
    result = consensus_graph.invoke(make_state())
    assert model.deliberation_prompts() == []
    assert len(result["rounds"]) == 1
    assert result["consensus"]["product_id"] == "B"
    assert result["consensus"]["agreement"] == 1.0
    assert result["consensus"]["dissent"] == []


def test_majority_still_deliberates_and_can_reach_unanimity(scripted):
    model = scripted({"budget": ["B"], "quality": ["C", "B"], "trust": ["B"], "deals": ["B"]})
    result = consensus_graph.invoke(make_state())
    assert len(model.deliberation_prompts()) == 4
    assert result["consensus"]["agreement_by_round"] == pytest.approx([3 / 4, 1.0])
    assert result["rounds"][1]["changed"] == ["quality"]
    assert result["consensus"]["unanimous"]
    assert result["consensus"]["deliberation_rounds"] == 1


def test_persistent_dissent_stops_at_round_limit(scripted):
    model = scripted({"budget": ["B"], "quality": ["C"], "trust": ["B"], "deals": ["B"]})
    result = consensus_graph.invoke(make_state())
    assert len(result["rounds"]) == 1 + deliberation.MAX_DELIBERATION_ROUNDS
    assert len(model.deliberation_prompts()) == 4 * deliberation.MAX_DELIBERATION_ROUNDS
    consensus = result["consensus"]
    assert consensus["product_id"] == "B"
    assert consensus["supporters"] == ["budget", "trust", "deals"]
    assert consensus["dissent"] == [
        {"agent": "quality", "product_id": "C", "reasoning": "quality reasoning"}
    ]


def test_consensus_product_is_from_eligible_catalog(scripted):
    scripted({"budget": ["B"], "quality": ["C"], "trust": ["C", "B"], "deals": ["B"]})
    result = consensus_graph.invoke(make_state())
    eligible_ids = {p["product_id"] for p in result["eligible_products"]}
    assert result["consensus"]["product_id"] in eligible_ids
    assert result["consensus"]["product"]["product_id"] == result["consensus"]["product_id"]


def test_deliberation_prompt_shows_other_agents_and_hides_over_budget_products(scripted):
    model = scripted({"budget": ["B"], "quality": ["C", "B"], "trust": ["B"], "deals": ["B"]})
    consensus_graph.invoke(make_state())
    quality_prompt = model.prompts["quality"][1]
    assert "budget reasoning" in quality_prompt
    assert "trust reasoning" in quality_prompt
    assert "deals reasoning" in quality_prompt
    assert "Premium Headphones" not in quality_prompt


def test_deliberation_rejects_unknown_product_ids(scripted):
    scripted({"budget": ["B"], "quality": ["C", "Z"], "trust": ["B"], "deals": ["B"]})
    with pytest.raises(ValueError, match="Unknown product ID"):
        consensus_graph.invoke(make_state())


def test_finalize_rejects_product_outside_catalog():
    state = make_state(
        eligible_products=[{"product_id": "B", "price": 149.0}],
        rounds=[{"round": 0, "recommendations": recs("Z", "Z", "Z", "Z"), "agreement": 1.0, "unanimous": True}],
    )
    with pytest.raises(ValueError, match="not in the eligible catalog"):
        finalize(state)
