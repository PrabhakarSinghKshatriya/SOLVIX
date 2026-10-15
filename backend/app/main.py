from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth.routes import router as auth_router
from app.api.workers.routes import router as workers_router
from app.api.requests.routes import router as requests_router
from app.api.notifications.routes import router as notifications_router
from app.api.subscriptions.routes import router as subscriptions_router
from app.api.admin.routes import router as admin_router
from app.api.stats.routes import router as stats_router
from app.api.aadhaar.routes import router as aadhaar_router
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

    # Allow only one review per service request.
    db["reviews"].create_index(
        [("request_id", 1)],
        unique=True,
        name="reviews_request_unique",
    )
    db["reviews"].create_index(
        [("worker_id", 1), ("created_at", -1)],
        name="reviews_worker_created",
    )

    # Support geospatial worker searches.
    workers_collection = db["workers"]
    has_location_index = any(
        index.get("key", {}).get("location") == "2dsphere"
        and len(index.get("key", {})) == 1
        for index in workers_collection.list_indexes()
    )
    if not has_location_index:
        workers_collection.create_index(
            [("location", "2dsphere")],
            name="worker_location_2dsphere",
        )

    logger.info("SOLVIX database indexes initialized successfully")

    db["notifications"].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="notifications_user_created"
    )
    db["notifications"].create_index(
        [("user_id", 1), ("is_read", 1)],
        name="notifications_user_unread"
    )

    # Payment indexes: enforce idempotency at the database level.
    db["payments"].create_index(
        [("razorpay_order_id", 1)],
        unique=True,
        name="payments_razorpay_order_unique",
    )
    db["subscriptions"].create_index(
        [("payment_id", 1)],
        unique=True,
        name="subscriptions_payment_unique",
    )
    db["payment_webhook_events"].create_index(
        [("event_id", 1)],
        unique=True,
        name="payment_webhook_event_unique",
        partialFilterExpression={"event_id": {"$type": "string"}},
    )

    logger.info("SOLVIX payment indexes initialized successfully")

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
app.include_router(notifications_router)
app.include_router(subscriptions_router)
app.include_router(admin_router)
app.include_router(stats_router)
app.include_router(aadhaar_router)


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
