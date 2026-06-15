from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, profile, research, tasks, notes,
    ai, dashboard, projects, finance, habits, media, admin,
    teaching, journal, bookmarks, certificates,
    goals, calendar, health, learning, contacts, timeline, voice_notes, search,
)
from app.api.v1.endpoints.location import router as location_router
from app.api.v1.endpoints.admin_location import router as admin_location_router
from app.api.v1.endpoints.connect import router as connect_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(research.router)
api_router.include_router(tasks.router)
api_router.include_router(notes.router)
api_router.include_router(ai.router)
api_router.include_router(dashboard.router)
api_router.include_router(projects.router)
api_router.include_router(finance.router)
api_router.include_router(habits.router)
api_router.include_router(media.router)
api_router.include_router(admin.router)
api_router.include_router(teaching.router)
api_router.include_router(journal.router)
api_router.include_router(bookmarks.router)
api_router.include_router(certificates.router)
api_router.include_router(goals.router)
api_router.include_router(calendar.router)
api_router.include_router(health.router)
api_router.include_router(learning.router)
api_router.include_router(contacts.router)
api_router.include_router(timeline.router)
api_router.include_router(voice_notes.router)
api_router.include_router(search.router)
api_router.include_router(location_router)
api_router.include_router(admin_location_router)
api_router.include_router(connect_router)
