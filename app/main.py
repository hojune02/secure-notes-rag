from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import health_router, notes_router, auth_router, admin_router, rag_router, ready_router

from app.core.logging import setup_logging
from app.middleware.request_id import RequestIDMiddleware

from app.middleware.security_headers import SecurityHeadersMiddleware

setup_logging(getattr(settings, "log_level", "INFO"))

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url="/openapi.json",
    swagger_ui_parameters={"useLocalAssets": True},
)
print("enabled:", {"useLocalAssets": True})

# For audit
app.add_middleware(RequestIDMiddleware)
# Fpr security
app.add_middleware(SecurityHeadersMiddleware)

# Versioned API prefix
app.include_router(health_router, prefix="/v1")
app.include_router(notes_router, prefix="/v1")
app.include_router(auth_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")
app.include_router(rag_router, prefix="/v1")
app.include_router(ready_router, prefix="/v1")


@app.get("/v1/version", tags=["meta"])
def version():
    return {"name": settings.app_name, "version": settings.app_version}
