from pydantic import BaseModel, Field

class ProductRecommendation(BaseModel):
    product_id: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    tradeoffs: list[str]


class DeliberationResponse(ProductRecommendation):
    response_to_others: str = Field(
        description="Which of the other agents' arguments changed your mind or not, and why"
    )
