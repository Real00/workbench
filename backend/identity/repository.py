from dataclasses import asdict

from pymongo import AsyncMongoClient

from identity.domain import DeviceBinding, DeviceRepository, User, UserRepository


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


class MongoDeviceRepository(DeviceRepository):
    def __init__(self, client: AsyncMongoClient, database: str):
        self.collection = client[database]["devices"]

    async def save(self, binding: DeviceBinding) -> None:
        # 设备与绑定一一对应（换账号登录即重新绑定），按 device_id 覆盖
        await self.collection.replace_one(
            {"device_id": binding.device_id},
            asdict(binding),
            upsert=True,
        )

    async def by_device(self, device_id: str) -> DeviceBinding | None:
        data = await self.collection.find_one({"device_id": device_id}, {"_id": 0})
        return DeviceBinding(**data) if data else None

    async def list_for_user(self, user_id: str) -> list[DeviceBinding]:
        cursor = self.collection.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
        return [DeviceBinding(**row) async for row in cursor]

    async def delete(self, user_id: str, binding_id: str) -> bool:
        deleted = await self.collection.delete_one({"user_id": user_id, "id": binding_id})
        return deleted.deleted_count > 0

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("device_id", unique=True)
        await self.collection.create_index("user_id")
