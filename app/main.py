from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth
from app.routes import folder

app = FastAPI(
    title="FastAPI Authentication API",
    description="Authentication & Folder Management System",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(folder.router)


# Root API
@app.get("/")
async def root():
    return {
        "success": True,
        "message": "FastAPI server is running"
    }


# Health Check
@app.get("/health")
async def health_check():
    return {
        "status": "OK"
    }