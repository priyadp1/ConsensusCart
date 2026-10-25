import json
from functools import lru_cache

from langchain.chat_models import init_chat_model

from agents.schema import ProductRecommendation


@lru_cache(maxsize=1)
def get_model():
    return init_chat_model(
        "openai:gpt-4.1-mini",
        temperature=0,
        max_tokens=1000,
    )


def format_products(products):
    return json.dumps(products, indent=2)


def validate_recommendation(recommendation: ProductRecommendation, products):
    valid_ids = {str(p["product_id"]) for p in products}
    if recommendation.product_id not in valid_ids:
        raise ValueError(f"Unknown product ID: {recommendation.product_id}")
    return recommendation.model_dump()
