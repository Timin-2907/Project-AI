from fastapi import APIRouter, Depends
from database_mongo import activity_logs, login_logs, folder_logs
from dependencies import get_current_user
from app.models import User   # ← sửa dòng này

router = APIRouter(prefix="/api/logs", tags=["Logs"])


def _fmt(doc: dict) -> dict:
    doc.pop("_id", None)
    if "timestamp" in doc and doc["timestamp"]:
        doc["timestamp"] = doc["timestamp"].strftime("%H:%M %d/%m/%Y")
    return doc


@router.get("/activity")
async def get_activity_logs(current_user: User = Depends(get_current_user)):
    cursor = activity_logs.find({"user_id": current_user.UserID}).sort("timestamp", -1).limit(50)
    results = []
    async for doc in cursor:
        results.append(_fmt(doc))
    return {"success": True, "count": len(results), "data": results}


@router.get("/login")
async def get_login_logs(current_user: User = Depends(get_current_user)):
    cursor = login_logs.find({"user_id": current_user.UserID}).sort("timestamp", -1).limit(50)
    results = []
    async for doc in cursor:
        results.append(_fmt(doc))
    return {"success": True, "count": len(results), "data": results}


@router.get("/folders")
async def get_folder_logs(current_user: User = Depends(get_current_user)):
    cursor = folder_logs.find({"user_id": current_user.UserID}).sort("timestamp", -1).limit(50)
    results = []
    async for doc in cursor:
        results.append(_fmt(doc))
    return {"success": True, "count": len(results), "data": results}


@router.get("/stats")
async def get_user_stats(current_user: User = Depends(get_current_user)):
    pipeline = [
        {"$match": {"user_id": current_user.UserID}},
        {"$group": {"_id": "$action", "count": {"$sum": 1}, "last": {"$max": "$timestamp"}}},
        {"$sort": {"count": -1}},
    ]
    results = []
    async for doc in folder_logs.aggregate(pipeline):
        results.append({
            "action":  doc["_id"],
            "count":   doc["count"],
            "last_at": doc["last"].strftime("%H:%M %d/%m/%Y") if doc["last"] else None,
        })
    return {"success": True, "data": results}