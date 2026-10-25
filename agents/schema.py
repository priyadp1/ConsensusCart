from pydantic import BaseModel, Field

class ProductRecommendation(BaseModel):
    product_id: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    tradeoffs: list[str]
