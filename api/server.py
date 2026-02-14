
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio

from config.settings import settings
from bot.telegram_handler import bot
from memory.memory_manager_async import memory_manager
from schemas import DiaryEntrySchema

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

@app.get("/api/memories/{user_id}", response_model=list[DiaryEntrySchema])
async def get_memories(user_id: int):
    """
    Fetch memories for a specific user.
    In a real app, you'd validate the WebApp parsing data to ensure security.
    For this prototype, we'll trust the user_id if this is a personal bot.
    """
    try:
        entries = await memory_manager.get_diary_entries(
            user_id=user_id,
            limit=50,
            entry_type="conversation_memory" # Only show processed memories
        )
        return entries
    except Exception as e:
        logger.error(f"Error fetching memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount Static Files (Frontend)
# We accept that the web folder might not exist yet during initial scaffolding
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

