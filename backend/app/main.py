from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth.routes import router as auth_router
from app.api.workers.routes import router as workers_router
from app.api.requests.routes import router as requests_router
from app.config import settings
from app.database.connection import check_database_connection, get_database


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_database()

    # Confirm that MongoDB is reachable before startup completes.
    db.command("ping")

    # Enforce unique email registrations.
    db["users"].create_index(
        [("email", 1)],
        unique=True,
        name="users_email_unique",
    )

    # Support geospatial worker searches.
    db["workers"].create_index(
        [("location", "2dsphere")],
        name="worker_location_2dsphere",
    )

    logger.info("SOLVIX database indexes initialized successfully")

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="SOLVIX Hyperlocal Service Marketplace API",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(workers_router)
app.include_router(requests_router)


@app.get("/")
def root():
    return {
        "success": True,
        "message": "Welcome to SOLVIX API",
        "version": settings.app_version,
    }


@app.get("/health")
def health():
    database_connected = check_database_connection()

    return {
        "status": "healthy" if database_connected else "degraded",
        "database": "connected" if database_connected else "disconnected",
    }
