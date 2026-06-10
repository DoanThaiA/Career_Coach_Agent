import os
from motor.motor_asyncio import AsyncIOMotorClient
from src.core.logger import get_logger

logger = get_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "recruitment_db")

class MongoDBClient:
    _client: AsyncIOMotorClient = None
    _db = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            logger.info(f"Khởi tạo MongoDB client tới {MONGO_URI}")
            cls._client = AsyncIOMotorClient(MONGO_URI)
            cls._db = cls._client[DB_NAME]
        return cls._client

    @classmethod
    def get_db(cls):
        if cls._db is None:
            cls.get_client()
        return cls._db

    @classmethod
    async def insert_cv(cls, cv_data: dict) -> str:
        """Lưu trữ cấu trúc CV vào MongoDB."""
        db = cls.get_db()
        collection = db["cv_documents"]
        result = await collection.insert_one(cv_data)
        logger.info(f"Đã lưu CV vào MongoDB với ID: {result.inserted_id}")
        return str(result.inserted_id)

    @classmethod
    async def insert_jd(cls, jd_data: dict) -> str:
        """Lưu trữ cấu trúc JD vào MongoDB."""
        db = cls.get_db()
        collection = db["jd_documents"]
        result = await collection.insert_one(jd_data)
        logger.info(f"Đã lưu JD vào MongoDB với ID: {result.inserted_id}")
        return str(result.inserted_id)

    @classmethod
    async def get_all_cvs(cls) -> list:
        db = cls.get_db()
        cursor = db["cv_documents"].find({}, {"full_name": 1, "original_file_path": 1, "created_at": 1}).sort("_id", -1)
        return [{"id": str(doc["_id"]), "name": doc.get("full_name") or doc.get("original_file_path", "Unknown")} async for doc in cursor]

    @classmethod
    async def get_cv_by_id(cls, cv_id: str) -> dict:
        from bson.objectid import ObjectId
        db = cls.get_db()
        doc = await db["cv_documents"].find_one({"_id": ObjectId(cv_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    @classmethod
    async def get_all_jds(cls) -> list:
        db = cls.get_db()
        cursor = db["jd_documents"].find({}, {"job_title": 1, "original_file_path": 1, "created_at": 1}).sort("_id", -1)
        return [{"id": str(doc["_id"]), "title": doc.get("job_title") or doc.get("original_file_path", "Unknown")} async for doc in cursor]

    @classmethod
    async def get_jd_by_id(cls, jd_id: str) -> dict:
        from bson.objectid import ObjectId
        db = cls.get_db()
        doc = await db["jd_documents"].find_one({"_id": ObjectId(jd_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

