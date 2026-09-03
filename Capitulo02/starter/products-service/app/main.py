from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

app = FastAPI(title="Products Service", version="1.0.0")
products: dict[int, "Product"] = {}
next_id = 1


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)


class Product(ProductCreate):
    id: int


@app.get("/products", response_model=list[Product])
def list_products() -> list[Product]:
    return list(products.values())


@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate) -> Product:
    global next_id
    product = Product(id=next_id, **payload.model_dump())
    products[next_id] = product
    next_id += 1
    return product


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int) -> Product:
    # TODO: devolver el producto o responder 404.
    raise HTTPException(status_code=501, detail="TODO")


@app.put("/products/{product_id}", response_model=Product)
def update_product(product_id: int, payload: ProductUpdate) -> Product:
    # TODO: aplicar únicamente los campos enviados o responder 404.
    raise HTTPException(status_code=501, detail="TODO")


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int) -> Response:
    # TODO: eliminar el producto o responder 404; una respuesta 204 no lleva cuerpo.
    raise HTTPException(status_code=501, detail="TODO")
