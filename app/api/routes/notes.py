import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User
from app.models.note import Note
from app.schemas.note import NoteCreate, NoteOut, NoteUpdate

from app.api.deps import get_current_user
from app.api.rate_limit import rate_limit_user

from app.services.audit import audit

router = APIRouter(prefix="/notes", tags=["notes"])


## Day 1 dev user logic is now eliminated. ##

# current_user_EMAIL = "dev@local"
# def get_or_create_current_user(db: Session) -> User:
#     user = db.scalar(select(User).where(User.email == current_user_EMAIL))
#     if user:
#         return user

#     user = User(
#         email=current_user_EMAIL,
#         password_hash=None,
#         role="user",
#         is_active=True,
#     )
#     db.add(user)
#     db.commit()
#     db.refresh(user)
#     return user


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit_user("notes", 60, 60))])
def create_note(payload: NoteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Day 1 feature is now gone.
    # current_user = get_or_create_current_user(db) 
    # Now we have get_current_user from Day 2.

    note = Note(
        owner_id=current_user.id,
        title=payload.title,
        content=payload.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    audit(db, current_user.id, "notes.create_note", {"role": current_user.role, "note_title": payload.title})

    return note


@router.get("", response_model=dict, dependencies=[Depends(rate_limit_user("notes", 60, 60))])
def list_notes(limit: int = 20, offset: int = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")


    total = db.scalar(select(func.count()).select_from(Note).where(Note.owner_id == current_user.id)) or 0
    notes = db.scalars(
        select(Note)
        .where(Note.owner_id == current_user.id)
        .order_by(Note.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "items": [NoteOut.model_validate(n).model_dump() for n in notes],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/{note_id}", response_model=NoteOut, dependencies=[Depends(rate_limit_user("notes", 60, 60))])
def get_note(note_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    note = db.scalar(select(Note).where(Note.id == note_id, Note.owner_id == current_user.id))
    if not note:
        raise HTTPException(status_code=404, detail="note not found")
    return note


@router.patch("/{note_id}", response_model=NoteOut, dependencies=[Depends(rate_limit_user("notes", 60, 60))])
def update_note(note_id: uuid.UUID, payload: NoteUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    note = db.scalar(select(Note).where(Note.id == note_id, Note.owner_id == current_user.id))
    if not note:
        raise HTTPException(status_code=404, detail="note not found")

    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content

    db.add(note)
    db.commit()
    db.refresh(note)

    audit(db, current_user.id, "notes.update_note", {"role": current_user.role, "note_title": note.title})
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(rate_limit_user("notes", 60, 60))])
def delete_note(note_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    note = db.scalar(select(Note).where(Note.id == note_id, Note.owner_id == current_user.id))
    if not note:
        raise HTTPException(status_code=404, detail="note not found")

    db.delete(note)
    db.commit()

    audit(db, current_user.id, "notes.delete_note", {"role": current_user.role, "note_title": note.title})

    return None
