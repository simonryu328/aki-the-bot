
import os
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio

from config.settings import settings
from bot.telegram_handler import bot
from memory.memory_manager_async import memory_manager
from memory.database_async import db
from memory.models import CalendarEvent
from schemas import DiaryEntrySchema, CalendarEventSchema, CalendarEventCreate
from telegram import Update
from sqlalchemy import select, delete as sa_delete

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI app.
    Starts and stops the Telegram bot alongside the API.
    """
    # Startup
    logger.info("Starting up FastAPI and Telegram Bot...")
    
    # Start the bot (handles initialization and polling/webhook setup)
    await bot.start()
    
    if settings.WEBHOOK_URL:
        await bot.application.bot.set_webhook(url=f"{settings.WEBHOOK_URL}/webhook/{settings.TELEGRAM_BOT_TOKEN}")
        
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await bot.stop()

app = FastAPI(title="AI Companion API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for now, restrict in prod if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints
@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/memories/{telegram_id}", response_model=list[DiaryEntrySchema])
async def get_memories(telegram_id: int):
    """
    Fetch memories for a specific user using their Telegram ID.
    In a real app, you'd validate the WebApp parsing data to ensure security.
    For this prototype, we'll trust the telegram_id if this is a personal bot.
    """
    try:
        # Get internal user ID from Telegram ID
        # use get_or_create to ensure we don't crash if new user opens app
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        
        entries = await memory_manager.get_diary_entries(
            user_id=user.id,
            limit=50,
            entry_type="conversation_memory" # Only show processed memories
        )
        return entries
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Calendar Endpoints ──────────────────────────────────────────────

@app.get("/api/calendar/{telegram_id}", response_model=list[CalendarEventSchema])
async def get_calendar_events(
    telegram_id: int,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
):
    """List calendar events, optionally filtered by date range."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        async with db.get_session() as session:
            stmt = select(CalendarEvent).where(CalendarEvent.user_id == user.id)
            if from_date:
                stmt = stmt.where(CalendarEvent.event_start >= from_date)
            if to_date:
                stmt = stmt.where(CalendarEvent.event_start <= to_date)
            stmt = stmt.order_by(CalendarEvent.event_start)
            result = await session.execute(stmt)
            events = result.scalars().all()
            return [CalendarEventSchema.model_validate(e) for e in events]
    except Exception as e:
        logger.error(f"Error fetching calendar events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calendar/{telegram_id}", response_model=CalendarEventSchema, status_code=201)
async def create_calendar_event(telegram_id: int, event: CalendarEventCreate):
    """Create a new calendar event."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        async with db.get_session() as session:
            db_event = CalendarEvent(
                user_id=user.id,
                title=event.title,
                description=event.description,
                event_start=event.event_start,
                event_end=event.event_end,
                is_all_day=event.is_all_day,
                source="manual",
            )
            session.add(db_event)
            await session.commit()
            await session.refresh(db_event)
            return CalendarEventSchema.model_validate(db_event)
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/calendar/{telegram_id}/{event_id}", status_code=204)
async def delete_calendar_event(telegram_id: int, event_id: int):
    """Delete a calendar event."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        async with db.get_session() as session:
            stmt = sa_delete(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == user.id,
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Event not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendar/{telegram_id}/upcoming", response_model=list[CalendarEventSchema])
async def get_upcoming_events(telegram_id: int):
    """Get events in the next 48 hours — used by reach-out scheduler."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=48)
        async with db.get_session() as session:
            stmt = (
                select(CalendarEvent)
                .where(
                    CalendarEvent.user_id == user.id,
                    CalendarEvent.event_start >= now,
                    CalendarEvent.event_start <= cutoff,
                )
                .order_by(CalendarEvent.event_start)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()
            return [CalendarEventSchema.model_validate(e) for e in events]
    except Exception as e:
        logger.error(f"Error fetching upcoming events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/{token}")
async def webhook_handler(token: str, request: Request):
    """
    Handle incoming Telegram updates via webhook.
    """
    if token != settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    try:
        data = await request.json()
        update = Update.de_json(data, bot.application.bot)
        await bot.application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount Static Files (Frontend)
# We accept that the web folder might not exist yet during initial scaffolding
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")
if os.path.exists(static_dir):
    logger.info(f"Serving static files from {static_dir}")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    logger.warning(f"Static directory not found: {static_dir}. Frontend will not be served.")


