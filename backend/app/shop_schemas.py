from datetime import datetime
from pydantic import BaseModel, Field

class ShopCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=80)
    enabled: bool = True

class ShopProductIn(BaseModel):
    category_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=280)
    description: str = Field(default="", max_length=12000)
    brand: str | None = Field(default=None, max_length=100)
    price_xof: float = Field(ge=0)
    original_price_xof: float | None = Field(default=None, ge=0)
    condition: str = Field(default="NEW", pattern="^(NEW|USED)$")
    stock_quantity: int = Field(default=0, ge=0)
    specifications: dict = Field(default_factory=dict)
    image_url: str | None = Field(default=None, max_length=2048)
    enabled: bool = True

class ShopOrderItemIn(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=99)

class ShopPublicOrderIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str = Field(min_length=5, max_length=50)
    delivery_address: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    payment_method: str | None = Field(default=None, max_length=50)
    items: list[ShopOrderItemIn] = Field(min_length=1, max_length=40)

class ShopOrderStatusIn(BaseModel):
    status: str = Field(pattern="^(PENDING|CONFIRMED|PROCESSING|READY|DELIVERED|CANCELLED)$")
    payment_status: str | None = Field(default=None, pattern="^(PENDING|PAID|REJECTED)$")
