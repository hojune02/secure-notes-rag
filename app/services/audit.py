from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

def audit(db: Session, actor_user_id, event_type: str, details: dict | None = None) -> None:
    db.add(AuditLog(actor_user_id=actor_user_id, event_type=event_type, details=details))
    db.commit()
