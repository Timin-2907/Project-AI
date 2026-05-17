from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

mongo_client = AsyncIOMotorClient(settings.MONGO_URL)
mongo_db     = mongo_client["auth_logs"]

activity_logs = mongo_db["activity_logs"]
login_logs    = mongo_db["login_logs"]
folder_logs   = mongo_db["folder_logs"]


async def init_mongo_indexes():
    await activity_logs.create_index([("user_id", 1), ("timestamp", -1)])
    await login_logs.create_index([("user_id", 1), ("timestamp", -1)])
    await folder_logs.create_index([("user_id", 1), ("timestamp", -1)])
    print("✅ MongoDB indexes created")


async def log_folder_action(user_id: int, action: str, folder_name: str, detail: dict = {}):
    from datetime import datetime
    try:
        await folder_logs.insert_one({
            "user_id":     user_id,
            "action":      action,
            "folder_name": folder_name,
            "detail":      detail,
            "timestamp":   datetime.utcnow(),
        })
    except Exception as e:
        print(f"[MongoDB] Folder log error: {e}")


async def log_activity(user_id: int, email: str, action: str, detail: dict = {}):
    from datetime import datetime
    try:
        await activity_logs.insert_one({
            "user_id":   user_id,
            "email":     email,
            "action":    action,
            "detail":    detail,
            "timestamp": datetime.utcnow(),
        })
    except Exception as e:
        print(f"[MongoDB] Activity log error: {e}")