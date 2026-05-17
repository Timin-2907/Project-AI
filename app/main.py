import sys
sys.path.insert(0, "/app")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from database_mongo import init_mongo_indexes

from app.models import User          # noqa
from app.models_folder import Folder # noqa

from app.routes.auth   import router as auth_router
from app.routes.folder import router as folder_router
from app.routes.logs   import router as logs_router

app = FastAPI(title="Auth System API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ PostgreSQL tables ready")
    await init_mongo_indexes()

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()

app.include_router(auth_router)
app.include_router(folder_router)
app.include_router(logs_router)

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "OK", "version": "2.0.0"}