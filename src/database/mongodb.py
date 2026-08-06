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
    async def ensure_indexes(cls) -> None:
        """Tạo indexes khi khởi động server — chạy 1 lần, idempotent."""
        db = cls.get_db()
        await db["cv_documents"].create_index([("_id", 1)])
        await db["cv_documents"].create_index([("task_id", 1)])
        await db["jd_documents"].create_index([("_id", 1)])
        await db["jd_documents"].create_index([("task_id", 1)])
        logger.info("✔ MongoDB indexes đã được tạo")

    @classmethod
    async def get_all_cvs(cls) -> list:
        db = cls.get_db()
        # Lấy cả candidate_info lẫn original_file_path để có tên hiển thị đúng
        cursor = db["cv_documents"].find(
            {},
            {"candidate_info": 1, "original_file_path": 1, "created_at": 1}
        ).sort("_id", -1)
        result = []
        async for doc in cursor:
            # Thử lấy full_name từ candidate_info trước, fallback về file path
            candidate_info = doc.get("candidate_info") or {}
            name = (
                candidate_info.get("full_name")
                or doc.get("original_file_path", "Unknown")
            )
            result.append({"id": str(doc["_id"]), "name": name})
        return result

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

    @classmethod
    async def update_cv(cls, cv_id: str, cv_data: dict) -> bool:
        """Cập nhật dữ liệu CV."""
        from bson.objectid import ObjectId
        db = cls.get_db()
        
        # Bỏ đi _id và id nếu có trong data update để tránh lỗi Mongo
        update_data = cv_data.copy()
        update_data.pop("_id", None)
        update_data.pop("id", None)
        
        result = await db["cv_documents"].update_one(
            {"_id": ObjectId(cv_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    @classmethod
    async def update_jd(cls, jd_id: str, jd_data: dict) -> bool:
        """Cập nhật dữ liệu JD."""
        from bson.objectid import ObjectId
        db = cls.get_db()
        
        # Bỏ đi _id và id nếu có trong data update để tránh lỗi Mongo
        update_data = jd_data.copy()
        update_data.pop("_id", None)
        update_data.pop("id", None)
        
        result = await db["jd_documents"].update_one(
            {"_id": ObjectId(jd_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    @classmethod
    async def delete_cv(cls, cv_id: str) -> bool:
        """Xóa một CV khỏi MongoDB."""
        from bson.objectid import ObjectId
        db = cls.get_db()
        result = await db["cv_documents"].delete_one({"_id": ObjectId(cv_id)})
        return result.deleted_count > 0

    @classmethod
    async def delete_jd(cls, jd_id: str) -> bool:
        """Xóa một JD khỏi MongoDB."""
        from bson.objectid import ObjectId
        db = cls.get_db()
        result = await db["jd_documents"].delete_one({"_id": ObjectId(jd_id)})
        return result.deleted_count > 0

