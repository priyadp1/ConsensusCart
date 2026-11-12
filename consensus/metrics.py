from collections import Counter


def count_votes(recommendations):
    return Counter(rec["product_id"] for rec in recommendations.values())


def calculate_agreement(recommendations):
    counts = count_votes(recommendations)
    return max(counts.values()) / len(recommendations)


def is_unanimous(recommendations):
    return len(count_votes(recommendations)) == 1


def confidence_by_product(recommendations):
    totals = Counter()
    for rec in recommendations.values():
        totals[rec["product_id"]] += rec["confidence"]
    return dict(totals)


def changed_agents(previous, current):
    return [
        agent for agent, rec in current.items()
        if agent in previous and previous[agent]["product_id"] != rec["product_id"]
    ]
