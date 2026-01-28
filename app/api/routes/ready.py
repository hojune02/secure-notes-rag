from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.rate_limiter import get_redis  # adjust if your project names differ

router = APIRouter(tags=["health"])


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    # DB check
    db.execute(text("SELECT 1"))

    # Redis check (if rate limiting uses Redis)
    r = get_redis()
    r.ping()

    return {"status": "ready"}
