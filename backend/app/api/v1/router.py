from fastapi import APIRouter

from app.api.v1 import admin, analytics, auth, realtime, records, thresholds, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(records.router)
api_router.include_router(analytics.router)
api_router.include_router(realtime.router)
api_router.include_router(realtime.ws_router)
api_router.include_router(thresholds.router)
api_router.include_router(admin.router)
