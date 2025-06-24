from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from datetime import datetime
import os

# =============== DATABASE SETUP ===============

DATABASE_URL = os.getenv("EVENT_MANAGER_DB_URL", "sqlite:///./events.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EventDB(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(128), index=True, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create database tables
Base.metadata.create_all(bind=engine)


# =============== SCHEMA DEFINITIONS ===============

class EventBase(BaseModel):
    title: str = Field(..., description="Title of the event", max_length=128)
    description: Optional[str] = Field(None, description="Description of the event")
    start_time: datetime = Field(..., description="Start date and time of the event")
    end_time: datetime = Field(..., description="End date and time of the event")
    location: Optional[str] = Field(None, description="Location of the event", max_length=256)

    class Config:
        orm_mode = True


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Title of the event", max_length=128)
    description: Optional[str] = Field(None, description="Description of the event")
    start_time: Optional[datetime] = Field(None, description="Start date and time of the event")
    end_time: Optional[datetime] = Field(None, description="End date and time of the event")
    location: Optional[str] = Field(None, description="Location of the event", max_length=256)

    class Config:
        orm_mode = True


class Event(EventBase):
    id: int = Field(..., description="Unique identifier for the event")
    created_at: datetime
    updated_at: datetime


# =============== BUSINESS LOGIC ===============

def get_db():
    """Yields an SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# PUBLIC_INTERFACE
def create_event(db: Session, event: EventCreate) -> EventDB:
    """Create a new event in the database."""
    db_event = EventDB(**event.dict())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


# PUBLIC_INTERFACE
def get_event(db: Session, event_id: int) -> Optional[EventDB]:
    """Retrieve an event by ID."""
    return db.query(EventDB).filter(EventDB.id == event_id).first()


# PUBLIC_INTERFACE
def get_all_events(db: Session, skip: int = 0, limit: int = 100) -> List[EventDB]:
    """Retrieve all events with pagination."""
    return db.query(EventDB).offset(skip).limit(limit).all()


# PUBLIC_INTERFACE
def update_event(db: Session, event_id: int, event_update: EventUpdate) -> Optional[EventDB]:
    """Update an existing event."""
    db_event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not db_event:
        return None
    update_data = event_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_event, key, value)
    db.commit()
    db.refresh(db_event)
    return db_event


# PUBLIC_INTERFACE
def delete_event(db: Session, event_id: int) -> bool:
    """Delete an event."""
    db_event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not db_event:
        return False
    db.delete(db_event)
    db.commit()
    return True


# =============== FASTAPI APP & ROUTES ===============

app = FastAPI(
    title="Event Manager Backend API",
    description=(
        "REST API backend for managing events. "
        "Allows creating, updating, deleting, and querying events."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Events", "description": "Operations for managing events"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Health check endpoint to verify that the backend is running."
)
def health_check():
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post(
    "/events",
    response_model=Event,
    status_code=status.HTTP_201_CREATED,
    tags=["Events"],
    summary="Create Event",
    description="Create a new event."
)
def api_create_event(event: EventCreate, db: Session = Depends(get_db)):
    db_event = create_event(db, event)
    return db_event


# PUBLIC_INTERFACE
@app.get(
    "/events",
    response_model=List[Event],
    tags=["Events"],
    summary="Get Events",
    description="Get a list of all events, with optional pagination."
)
def api_get_events(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    events = get_all_events(db, skip=skip, limit=limit)
    return events


# PUBLIC_INTERFACE
@app.get(
    "/events/{event_id}",
    response_model=Event,
    tags=["Events"],
    summary="Get Event by ID",
    description="Get details of an event by its ID."
)
def api_get_event(event_id: int, db: Session = Depends(get_db)):
    db_event = get_event(db, event_id)
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    return db_event


# PUBLIC_INTERFACE
@app.put(
    "/events/{event_id}",
    response_model=Event,
    tags=["Events"],
    summary="Update Event",
    description="Update the details of an event."
)
def api_update_event(
    event_id: int,
    event_update: EventUpdate,
    db: Session = Depends(get_db)
):
    db_event = update_event(db, event_id, event_update)
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    return db_event


# PUBLIC_INTERFACE
@app.delete(
    "/events/{event_id}",
    response_model=dict,
    tags=["Events"],
    summary="Delete Event",
    description="Delete an event."
)
def api_delete_event(event_id: int, db: Session = Depends(get_db)):
    success = delete_event(db, event_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    return {"detail": "Event deleted successfully"}
