
import os
import logging
from datetime import datetime, timedelta
import pytz
import json
import random
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Query, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio

from config.settings import settings
from bot.telegram_handler import bot
from memory.memory_manager_async import memory_manager
from memory.database_async import db
from memory.models import FutureEntry
from agents.soul_agent import soul_agent
from schemas import DiaryEntrySchema, FutureEntrySchema, FutureEntryCreate, DailyMessageSchema
from telegram import Update, Message
from sqlalchemy import select, delete as sa_delete
from utils.spotify_manager import spotify_manager
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse

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


# ── User Profile Endpoints ──────────────────────────────────────────

class UserProfileResponse(BaseModel):
    id: int
    telegram_id: int
    name: Optional[str] = None
    timezone: str
    onboarding_state: Optional[str] = None

class SetupRequest(BaseModel):
    timezone: str
    name: Optional[str] = None

class DashboardResponse(BaseModel):
    profile: UserProfileResponse
    memories: list[DiaryEntrySchema]
    daily_message: DailyMessageSchema
    soundtrack: dict
    insights: dict
    horizons: list[FutureEntrySchema]

@app.get("/api/user/{telegram_id}", response_model=UserProfileResponse)
async def get_user_profile(telegram_id: int):
    """Get user profile for the mini app (onboarding state, timezone, etc.)."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        return UserProfileResponse(
            id=user.id,
            telegram_id=telegram_id,
            name=user.name,
            timezone=user.timezone or settings.TIMEZONE,
            onboarding_state=user.onboarding_state,
        )
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/user/{telegram_id}/setup")
async def complete_user_setup(telegram_id: int, req: SetupRequest):
    """
    Called by the mini app to complete onboarding.
    Sets the user's name, timezone (auto-detected by JS), and marks onboarding as complete.
    """
    try:
        import pytz
        # Validate timezone
        try:
            pytz.timezone(req.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise HTTPException(status_code=400, detail=f"Invalid timezone: {req.timezone}")

        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)

        # Update name and timezone
        await db.update_user_profile(
            user_id=user.id,
            name=req.name or user.name,
            timezone=req.timezone,
        )

        # Mark onboarding complete
        await db.update_user_onboarding_state(telegram_id=telegram_id, onboarding_state=None)

        # Evict user from cache so changes take effect immediately
        if user.id in memory_manager._user_cache:
            del memory_manager._user_cache[user.id]

        logger.info(f"User {telegram_id} completed setup via mini app (name={req.name}, tz={req.timezone})")
        return {"status": "ok", "name": req.name, "timezone": req.timezone}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing user setup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Spotify Integration Endpoints ─────────────────────────────────────

@app.get("/api/spotify/login/{telegram_id}")
async def spotify_login(telegram_id: int):
    """Initiate Spotify OAuth flow."""
    auth_url = spotify_manager.get_auth_url(state=str(telegram_id))
    if not auth_url:
        raise HTTPException(status_code=500, detail="Spotify integration not configured.")
    return {"url": auth_url}


@app.get("/api/spotify/callback")
async def spotify_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Handle Spotify OAuth callback."""
    if error:
        logger.error(f"Spotify returned an error in callback: {error}")
        return RedirectResponse(url=f"{settings.MINIAPP_URL or ''}/?spotify=error&reason={error}")

    if not code or not state:
        logger.error("Spotify callback missing code or state")
        return RedirectResponse(url=f"{settings.MINIAPP_URL or ''}/?spotify=error&reason=missing_data")

    try:
        # State should be the telegram_id string
        try:
            telegram_id = int(state)
        except ValueError:
            logger.error(f"Invalid state (not an int): {state}")
            return RedirectResponse(url=f"{settings.MINIAPP_URL or ''}/?spotify=error&reason=invalid_state")

        token_info = await spotify_manager.get_token_from_code(code)
        
        if not token_info:
            logger.error(f"Failed to retrieve token from Spotify for user {telegram_id}")
            return RedirectResponse(url=f"{settings.MINIAPP_URL or ''}/?spotify=error&reason=token_failure")
            
        # Store tokens in DB
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        
        # Calculate expiry
        expires_in = token_info.get('expires_in', 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        await db.update_user_spotify_tokens(
            user_id=user.id,
            access_token=token_info['access_token'],
            refresh_token=token_info['refresh_token'],
            expires_at=expires_at
        )

        # CRITICAL: Evict from memory manager cache to ensure fresh state
        if user.id in memory_manager._user_cache:
            del memory_manager._user_cache[user.id]
            logger.info(f"Evicted user {user.id} from cache post-Spotify connect")
        
        logger.info(f"Successfully connected Spotify for user {telegram_id}")
        
        # Return a success HTML page instead of a raw redirect. 
        # This prevents the "App in Safari" issue and gives user a clear path back.
        return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Aki Connected!</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: -apple-system, system-ui; text-align: center; padding: 40px; background: #000; color: white; }}
                    .card {{ background: #111; padding: 30px; border-radius: 20px; border: 1px solid #333; }}
                    .btn {{ display: inline-block; background: #1DB954; color: white; text-decoration: none; 
                           padding: 15px 30px; border-radius: 30px; font-weight: bold; margin-top: 20px; }}
                    h1 {{ color: #1DB954; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Aki is Connected!</h1>
                    <p>I can now hear the music in your head. 🎵</p>
                    <p>You can close this window and go back to Telegram.</p>
                    <a href="https://t.me/AkiTheBot" class="btn">Back to Aki</a>
                </div>
            </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"Critical error in Spotify callback: {e}", exc_info=True)
        return HTMLResponse(content="<h1>Connection Failed</h1><p>Something went wrong. Please try again from the app.</p>", status_code=500)


@app.post("/api/spotify/disconnect/{telegram_id}")
async def spotify_disconnect(telegram_id: int):
    """Disconnect user's Spotify account."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        
        # 1. Clear tokens in DB
        await db.update_user_spotify_tokens(
            user_id=user.id,
            access_token=None,
            refresh_token=None,
            expires_at=None
        )
        
        # 2. Delete today's soundtrack entry if it exists (for the clean slate)
        import pytz
        user_tz = pytz.timezone(user.timezone or settings.TIMEZONE)
        now_user = datetime.now(user_tz)
        today_start_user = now_user.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Delete any soundtrack entries from today
        async with db.get_session() as session:
            from sqlalchemy import delete
            from memory.models import DiaryEntry
            # We convert the cutoff back to UTC for the query
            cutoff_utc = today_start_user.astimezone(pytz.utc).replace(tzinfo=None)
            
            stmt = delete(DiaryEntry).where(
                DiaryEntry.user_id == user.id,
                DiaryEntry.entry_type == "daily_soundtrack",
                DiaryEntry.timestamp >= cutoff_utc
            )
            await session.execute(stmt)
            await session.commit()

        # 3. Evict from memory cache
        if user.id in memory_manager._user_cache:
            del memory_manager._user_cache[user.id]
            
        logger.info(f"Disconnected Spotify and cleared cache for user {telegram_id}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error disconnecting Spotify: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/spotify/status/{telegram_id}")
async def get_spotify_status(telegram_id: int):
    """Check if user has connected Spotify."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        return {
            "connected": user.spotify_refresh_token is not None,
            "expires_at": user.spotify_token_expires_at
        }
    except Exception as e:
        logger.error(f"Error checking Spotify status: {e}")
        return {"connected": False}

# ── Dashboard & Memory Helpers ──────────────────────────────────────────

async def _get_daily_message_data(telegram_id: int, user_schema) -> DailyMessageSchema:
    """Helper to fetch or generate daily message data."""
    try:
        user_tz = pytz.timezone(user_schema.timezone or settings.TIMEZONE)
        now_user = datetime.now(user_tz)
        today_start_user = now_user.replace(hour=0, minute=0, second=0, microsecond=0)
        
        entries = await memory_manager.get_diary_entries(
            user_id=user_schema.id,
            limit=1,
            entry_type="daily_message"
        )
        
        if entries:
            last_msg = entries[0]
            last_msg_local = last_msg.timestamp.replace(tzinfo=pytz.utc).astimezone(user_tz)
            if last_msg_local >= today_start_user:
                return DailyMessageSchema(
                    content=last_msg.content,
                    timestamp=last_msg.timestamp,
                    is_fallback="Fallback" in last_msg.title
                )

        content, is_fallback = await soul_agent.generate_daily_message(user_schema.id)
        await memory_manager.add_diary_entry(
            user_id=user_schema.id,
            entry_type="daily_message",
            title="Daily Message" if not is_fallback else "Daily Message (Fallback)",
            content=content,
            importance=10 if not is_fallback else 5
        )
        return DailyMessageSchema(
            content=content,
            timestamp=datetime.utcnow(),
            is_fallback=is_fallback
        )
    except Exception as e:
        logger.error(f"Error in _get_daily_message_data: {e}")
        from prompts import FALLBACK_QUOTES
        return DailyMessageSchema(
            content=random.choice(FALLBACK_QUOTES),
            timestamp=datetime.utcnow(),
            is_fallback=True
        )

async def _get_daily_soundtrack_data(telegram_id: int, user_schema) -> dict:
    """Helper to fetch or generate daily soundtrack data."""
    try:
        if not user_schema.spotify_refresh_token:
            return {"connected": False}

        user_tz = pytz.timezone(user_schema.timezone or settings.TIMEZONE)
        now_user = datetime.now(user_tz)
        today_start_user = now_user.replace(hour=0, minute=0, second=0, microsecond=0)

        entries = await memory_manager.get_diary_entries(
            user_id=user_schema.id,
            limit=1,
            entry_type="daily_soundtrack"
        )
        
        if entries:
            last_entry = entries[0]
            last_entry_local = last_entry.timestamp.replace(tzinfo=pytz.utc).astimezone(user_tz)
            if last_entry_local >= today_start_user:
                return json.loads(last_entry.content)

        data = await soul_agent.generate_daily_soundtrack(user_schema.id)
        if data.get("connected") and not data.get("error"):
            await memory_manager.add_diary_entry(
                user_id=user_schema.id,
                entry_type="daily_soundtrack",
                title="Daily Soundtrack",
                content=json.dumps(data),
                importance=7
            )
        return data
    except Exception as e:
        logger.error(f"Error in _get_daily_soundtrack_data: {e}")
        return {"connected": False, "error": str(e)}

async def _get_personalized_insights_data(telegram_id: int, user_schema) -> dict:
    """Helper to fetch or generate personalized insights data."""
    try:
        entries = await memory_manager.get_diary_entries(
            user_id=user_schema.id,
            limit=1,
            entry_type="personalized_insights"
        )
        
        should_regenerate = False
        if entries:
            last_entry = entries[0]
            try:
                cached_data = json.loads(last_entry.content)
                new_msg_count = await memory_manager.db.get_message_count_after(
                    user_id=user_schema.id,
                    after=last_entry.timestamp,
                    role="user"
                )
                if new_msg_count >= 50:
                    should_regenerate = True
                else:
                    return cached_data
            except:
                should_regenerate = True
        else:
            should_regenerate = True

        if should_regenerate:
            return await soul_agent.generate_personalized_insights(user_schema.id, store=True)

    except Exception as e:
        logger.error(f"Error in _get_personalized_insights_data: {e}")
    
    return {
        "unhinged_quotes": [],
        "aki_observations": [{"title": "Thinking...", "description": "Gathering more memories of you.", "emoji": "🤔"}],
        "fun_questions": ["What's on your mind today?"],
        "personal_stats": {"current_vibe": "New Friend", "top_topic": "Interests"}
    }

@app.get("/api/dashboard/{telegram_id}", response_model=DashboardResponse)
async def get_dashboard(telegram_id: int):
    """
    Unified endpoint for the Mini App dashboard.
    Fetches everything needed for the initial load in one round-trip.
    Uses sequential fetching for stability.
    """
    try:
        user_schema = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        
        # Sequential fetching for absolute stability
        memories = await memory_manager.get_diary_entries(
            user_id=user_schema.id,
            limit=50,
            entry_type="conversation_memory"
        )
        
        daily_msg = await _get_daily_message_data(telegram_id, user_schema)
        soundtrack = await _get_daily_soundtrack_data(telegram_id, user_schema)
        insights = await _get_personalized_insights_data(telegram_id, user_schema)
        horizons = await memory_manager.get_future_entries(user_id=user_schema.id)
        
        return DashboardResponse(
            profile=UserProfileResponse(
                id=user_schema.id,
                telegram_id=telegram_id,
                name=user_schema.name,
                timezone=user_schema.timezone or settings.TIMEZONE,
                onboarding_state=user_schema.onboarding_state,
            ),
            memories=memories,
            daily_message=daily_msg,
            soundtrack=soundtrack,
            insights=insights,
            horizons=horizons
        )
    except Exception as e:
        logger.error(f"Error fetching dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

@app.get("/api/daily-message/{telegram_id}", response_model=DailyMessageSchema)
async def get_daily_message(telegram_id: int):
    """Legacy individual endpoint (now maps to internal helper)."""
    user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
    return await _get_daily_message_data(telegram_id, user)


@app.get("/api/spotify/daily-soundtrack/{telegram_id}")
async def get_daily_soundtrack(telegram_id: int):
    """Legacy individual endpoint (now maps to internal helper)."""
    user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
    data = await _get_daily_soundtrack_data(telegram_id, user)
    return JSONResponse(content=data, headers={"Cache-Control": "no-cache"})


@app.get("/api/personalized-insights/{telegram_id}")
async def get_personalized_insights(telegram_id: int):
    """Legacy individual endpoint (now maps to internal helper)."""
    user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
    return await _get_personalized_insights_data(telegram_id, user)


@app.post("/api/ask-question/{telegram_id}")
async def ask_question(telegram_id: int, payload: dict):
    """
    Handle a user clicking a suggested question.
    1. Triggers orchestrator to process the question.
    2. Sends the response messages through the Telegram bot.
    """
    try:
        from bot.telegram_handler import bot
        from agents.orchestrator import orchestrator
        
        question = payload.get("question")
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        
        # 1. Send the question back to the chat so there's context
        # Format as an italicized quote to distinguish from the response
        prompt_text = f"_You asked:_ *{question}*"
        await bot._send_with_typing(chat_id=telegram_id, text=prompt_text)

        # 2. Let the bot "think" it received this message
        messages, emoji = await orchestrator.process_message(
            telegram_id=telegram_id,
            message=question,
            name=user.name,
            username=user.username,
        )

        # 3. Send the responses with typing animation
        for msg in messages:
            await bot._send_with_typing(chat_id=telegram_id, text=msg)
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing question trigger: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/future/{telegram_id}", response_model=list[FutureEntrySchema])
async def get_future_entries(
    telegram_id: int,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    entry_type: Optional[str] = Query(None),
):
    """List future entries (plans and notes), optionally filtered."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        entries = await memory_manager.get_future_entries(
            user_id=user.id,
            from_date=from_date,
            to_date=to_date,
            entry_type=entry_type
        )
        return entries
    except Exception as e:
        logger.error(f"Error fetching future entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/future/{telegram_id}", response_model=FutureEntrySchema, status_code=201)
async def create_future_entry(telegram_id: int, entry: FutureEntryCreate):
    """Create a new future entry (plan or note)."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        db_entry = await memory_manager.add_future_entry(
            user_id=user.id,
            entry_type=entry.entry_type,
            title=entry.title,
            content=entry.content,
            start_time=entry.start_time,
            end_time=entry.end_time,
            is_all_day=entry.is_all_day,
            source="manual"
        )
        return db_entry
    except Exception as e:
        logger.error(f"Error creating future entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/future/{telegram_id}/{entry_id}", response_model=FutureEntrySchema)
async def update_future_entry(telegram_id: int, entry_id: int, payload: dict):
    """Update a future entry (e.g. mark as completed)."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        updated = await memory_manager.update_future_entry(
            entry_id=entry_id,
            title=payload.get("title"),
            content=payload.get("content"),
            is_completed=payload.get("is_completed"),
            start_time=payload.get("start_time")
        )
        return updated
    except Exception as e:
        logger.error(f"Error updating future entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/future/{telegram_id}/{entry_id}", status_code=204)
async def delete_future_entry(telegram_id: int, entry_id: int):
    """Delete a future entry."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        success = await memory_manager.delete_future_entry(user_id=user.id, entry_id=entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting future entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/future/{telegram_id}/upcoming", response_model=list[FutureEntrySchema])
async def get_upcoming_plans(telegram_id: int):
    """Get plans in the next 48 hours."""
    try:
        user = await memory_manager.get_or_create_user(telegram_id=telegram_id)
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=48)
        entries = await memory_manager.get_future_entries(
            user_id=user.id,
            from_date=now,
            to_date=cutoff,
            entry_type="plan"
        )
        return entries
    except Exception as e:
        logger.error(f"Error fetching upcoming plans: {e}")
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
# Priority:
# 1. frontend/dist (Modern TS version)
# 2. web (Legacy Vanilla version)
base_dir = os.path.dirname(os.path.dirname(__file__))
modern_static_dir = os.path.join(base_dir, "frontend", "dist")
legacy_static_dir = os.path.join(base_dir, "web")

if os.path.exists(modern_static_dir):
    logger.info(f"Serving modern frontend from {modern_static_dir}")
    app.mount("/", StaticFiles(directory=modern_static_dir, html=True), name="static")
elif os.path.exists(legacy_static_dir):
    logger.info(f"Serving legacy frontend from {legacy_static_dir}")
    app.mount("/", StaticFiles(directory=legacy_static_dir, html=True), name="static")
else:
    logger.warning(f"No static directory found (checked {modern_static_dir} and {legacy_static_dir}). Frontend will not be served.")


