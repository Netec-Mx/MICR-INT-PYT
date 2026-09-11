import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Persistent Products Service", version="2.0.0")
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_FILE = DATA_DIR / "products.json"


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class Product(ProductCreate):
    id: int


def load_store() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        return {"next_id": 1, "products": []}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_store(store: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = DATA_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DATA_FILE)


@app.get("/products", response_model=list[Product])
def list_products() -> list[Product]:
    return [Product(**item) for item in load_store()["products"]]


@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate) -> Product:
    store = load_store()
    product = Product(id=store["next_id"], **payload.model_dump())
    store["next_id"] += 1
    store["products"].append(product.model_dump())
    save_store(store)
    return product


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int) -> Product:
    for item in load_store()["products"]:
        if item["id"] == product_id:
            return Product(**item)
    raise HTTPException(status_code=404, detail="Product not found")
