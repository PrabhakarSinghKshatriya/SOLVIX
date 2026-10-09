from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth.routes import router as auth_router
from app.api.workers.routes import router as workers_router
from app.api.requests.routes import router as requests_router

from app.config import settings
from app.database.connection import check_database_connection


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="SOLVIX Hyperlocal Service Marketplace API",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {
        "success": True,
        "message": "Welcome to SOLVIX API",
        "version": settings.app_version,
    }
app.include_router(workers_router)
app.include_router(requests_router)

@app.get("/health")
async def health():
    database_status = check_database_connection()

    return {
        "success": True,
        "service": "SOLVIX API",
        "status": "healthy",
        "database": "connected" if database_status else "disconnected",
    }
