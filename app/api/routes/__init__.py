from app.api.routes.health import router as health_router
from app.api.routes.notes import router as notes_router
from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.rag import router as rag_router
from app.api.routes.ready import router as ready_router

__all__ = ["health_router", "notes_router", "auth_router", "admin_router", "rag_router", "ready_router"]
