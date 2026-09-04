from dataclasses import asdict

from pymongo import AsyncMongoClient

from identity.domain import User, UserRepository


class MongoUserRepository(UserRepository):
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["users"]

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def save(self, user: User) -> None:
        await self.collection.replace_one({"id": user.id}, asdict(user), upsert=True)

    async def by_id(self, user_id: str) -> User | None:
        data = await self.collection.find_one({"id": user_id}, {"_id": 0})
        return User(**data) if data else None

    async def by_username(self, username: str) -> User | None:
        data = await self.collection.find_one({"username": username}, {"_id": 0})
        return User(**data) if data else None

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("username", unique=True)
        await self.collection.create_index("id", unique=True)
