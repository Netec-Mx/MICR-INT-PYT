import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def clean_repository():
    main.products.clear()
    main.next_id = 1


def create_product():
    return client.post("/products", json={"name": "Keyboard", "price": 50, "stock": 3})


def test_list_is_initially_empty():
    assert client.get("/products").json() == []


def test_create_product():
    response = create_product()
    assert response.status_code == 201
    assert response.json()["id"] == 1


def test_rejects_invalid_price():
    response = client.post("/products", json={"name": "X", "price": 0, "stock": 1})
    assert response.status_code == 422


def test_get_existing_and_missing_product():
    product_id = create_product().json()["id"]
    assert client.get(f"/products/{product_id}").status_code == 200
    assert client.get("/products/999").status_code == 404


def test_partial_update_preserves_other_fields():
    product_id = create_product().json()["id"]
    response = client.put(f"/products/{product_id}", json={"stock": 9})
    assert response.status_code == 200
    assert response.json()["name"] == "Keyboard"
    assert response.json()["stock"] == 9


def test_update_missing_product_returns_404():
    assert client.put("/products/999", json={"stock": 2}).status_code == 404


def test_delete_returns_204_and_removes_product():
    product_id = create_product().json()["id"]
    response = client.delete(f"/products/{product_id}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/products/{product_id}").status_code == 404
