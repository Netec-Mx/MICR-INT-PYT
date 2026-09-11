import asyncio, os
from decimal import Decimal
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from sqlalchemy import delete
from app.models import Product
from app.repositories import MongoDetails, PostgresProducts, postgres_factory
from app.schemas import ProductInput
from app.service import CatalogService

PG = os.getenv("POSTGRES_URL", "postgresql+asyncpg://catalog:catalog-lab@localhost:5432/catalog")
MONGO = os.getenv("MONGO_URL", "mongodb://catalog:catalog-lab@localhost:27017/?authSource=admin")

async def main():
    engine, sessions = postgres_factory(PG); mongo = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=2000)
    try:
        await mongo.catalog_details.product_details.delete_many({"sku": "TV-4K-LAB"})
    except PyMongoError:
        # La limpieza no debe impedir demostrar la compensación con MongoDB caído.
        pass
    async with sessions() as session:
        await session.execute(delete(Product).where(Product.sku == "TV-4K-LAB")); await session.commit()
    service = CatalogService(PostgresProducts(sessions), MongoDetails(mongo))
    view = await service.create(ProductInput("TV-4K-LAB", "Televisor 4K", Decimal("899.99"), 12, "Pantalla UHD", {"size": 55}, ["tv", "4k"]))
    print(view)
    mongo.close(); await engine.dispose()

if __name__ == "__main__": asyncio.run(main())
