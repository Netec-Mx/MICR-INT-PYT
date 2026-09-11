from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

@dataclass(frozen=True)
class ProductInput:
    sku: str
    name: str
    price: Decimal
    stock: int
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class ProductView:
    id: str
    sku: str
    name: str
    price: Decimal
    stock: int
    description: str
    attributes: dict[str, Any]
    tags: list[str]

def detail_document(product_id: str, data: ProductInput) -> dict[str, Any]:
    document = asdict(data)
    for key in ("name", "price", "stock"):
        document.pop(key)
    document["product_id"] = product_id
    return document
