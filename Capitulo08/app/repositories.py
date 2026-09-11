from typing import Any, Protocol
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.models import Product
from app.schemas import ProductInput, detail_document

class SqlProducts(Protocol):
    async def add(self, data: ProductInput) -> dict[str, Any]: ...
    async def get(self, product_id: str) -> dict[str, Any] | None: ...
    async def delete(self, product_id: str) -> None: ...

class DocumentDetails(Protocol):
    async def add(self, product_id: str, data: ProductInput) -> None: ...
    async def get(self, product_id: str) -> dict[str, Any] | None: ...

class PostgresProducts:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]): self.sessions = sessions
    async def add(self, data):
        async with self.sessions() as session:
            product = Product(sku=data.sku, name=data.name, price=data.price, stock=data.stock)
            session.add(product); await session.commit(); await session.refresh(product)
            return {"id": product.id, "sku": product.sku, "name": product.name, "price": product.price, "stock": product.stock}
    async def get(self, product_id):
        async with self.sessions() as session:
            product = await session.scalar(select(Product).where(Product.id == product_id))
            return None if product is None else {"id": product.id, "sku": product.sku, "name": product.name, "price": product.price, "stock": product.stock}
    async def delete(self, product_id):
        async with self.sessions() as session:
            await session.execute(delete(Product).where(Product.id == product_id)); await session.commit()

class MongoDetails:
    def __init__(self, client: AsyncIOMotorClient): self.collection = client.catalog_details.product_details
    async def add(self, product_id, data):
        await self.collection.insert_one(detail_document(product_id, data))
    async def get(self, product_id):
        return await self.collection.find_one({"product_id": product_id}, {"_id": 0})

def postgres_factory(url):
    engine = create_async_engine(url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
