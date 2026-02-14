"""
FastAPI backend for Telegram Mini App - Memory Viewer
Provides secure API endpoints for users to view their conversation memories.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pytz

from config.settings import settings
from memory.database import db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aki Memory Viewer API",
    description="API for Telegram Mini App to view conversation memories",
    version="1.0.0"
)

# CORS configuration for Telegram Mini Apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://web.telegram.org", "https://telegram.org"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ==================== Pydantic Models ====================

class ConversationMessage(BaseModel):
    """Single conversation message"""
    role: str
    message: str
    timestamp: str
    thinking: Optional[str] = None


class DiaryEntryResponse(BaseModel):
    """Diary entry response"""
    id: int
    entry_type: str
    title: str
    content: str
    importance: int
    timestamp: str
    exchange_start: Optional[str] = None
    exchange_end: Optional[str] = None


class UserStats(BaseModel):
    """User statistics"""
    total_conversations: int
    total_diary_entries: int
    total_memories: int
    first_interaction: Optional[str]
    last_interaction: Optional[str]
    days_active: int


class MemoryTimeline(BaseModel):
    """Memory timeline entry"""
    date: str
    conversations: int
    memories: int
    diary_entries: int


# ==================== Authentication ====================

def verify_telegram_webapp_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """
    Verify Telegram WebApp init data signature.
    
    Args:
        init_data: The initData string from Telegram WebApp
        bot_token: Bot token for verification
        
    Returns:
        Parsed data if valid
        
    Raises:
        HTTPException: If signature is invalid
    """
    try:
        # Parse the init data
        parsed_data = parse_qs(init_data)
        
        # Extract hash
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            raise HTTPException(status_code=401, detail="Missing hash")
        
        # Remove hash from data for verification
        data_check_string_parts = []
        for key in sorted(parsed_data.keys()):
            if key != 'hash':
                value = parsed_data[key][0]
                data_check_string_parts.append(f"{key}={value}")
        
        data_check_string = '\n'.join(data_check_string_parts)
        
        # Create secret key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Verify hash
        if calculated_hash != received_hash:
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse user data
        result = {}
        for key, value in parsed_data.items():
            if key != 'hash':
                result[key] = value[0]
        
        return result
        
    except Exception as e:
        logger.error(f"Error verifying Telegram data: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


def get_user_from_init_data(init_data: str) -> int:
    """
    Extract and verify user ID from Telegram init data.
    
    Args:
        init_data: Telegram WebApp init data
        
    Returns:
        User's telegram_id
    """
    verified_data = verify_telegram_webapp_data(init_data, settings.TELEGRAM_BOT_TOKEN)
    
    # Parse user object
    import json
    user_data = json.loads(verified_data.get('user', '{}'))
    telegram_id = user_data.get('id')
    
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Invalid user data")
    
    return telegram_id


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "Aki Memory Viewer API"}


@app.get("/api/user/stats")
async def get_user_stats(
    authorization: str = Header(..., alias="Authorization")
) -> UserStats:
    """
    Get user statistics.
    
    Headers:
        Authorization: Telegram WebApp init data
    """
    # Extract init data from Bearer token
    init_data = authorization.replace("Bearer ", "")
    telegram_id = get_user_from_init_data(init_data)
    
    # Get user from database
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user['id']
    
    # Get statistics
    conversations = db.get_recent_conversations(user_id, limit=10000)
    diary_entries = db.get_diary_entries(user_id, limit=10000)
    
    # Count memory entries (conversation_memory type)
    memory_count = sum(1 for entry in diary_entries if entry.entry_type == 'conversation_memory')
    
    # Calculate days active
    first_interaction = user.get('created_at')
    last_interaction = user.get('last_interaction')
    days_active = 0
    
    if first_interaction and last_interaction:
        delta = last_interaction - first_interaction
        days_active = max(1, delta.days)
    
    return UserStats(
        total_conversations=len(conversations),
        total_diary_entries=len(diary_entries),
        total_memories=memory_count,
        first_interaction=first_interaction.isoformat() if first_interaction else None,
        last_interaction=last_interaction.isoformat() if last_interaction else None,
        days_active=days_active
    )


@app.get("/api/conversations")
async def get_conversations(
    authorization: str = Header(..., alias="Authorization"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
) -> List[ConversationMessage]:
    """
    Get conversation history.
    
    Headers:
        Authorization: Telegram WebApp init data
        
    Query Parameters:
        limit: Number of messages to return (1-500)
        offset: Offset for pagination
    """
    init_data = authorization.replace("Bearer ", "")
    telegram_id = get_user_from_init_data(init_data)
    
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user['id']
    
    # Get conversations with pagination
    conversations = db.get_recent_conversations(user_id, limit=limit + offset)
    
    # Apply offset
    conversations = conversations[offset:offset + limit]
    
    # Convert to response format
    result = []
    for conv in conversations:
        result.append(ConversationMessage(
            role=conv.role,
            message=conv.message,
            timestamp=conv.timestamp.isoformat(),
            thinking=conv.thinking if hasattr(conv, 'thinking') else None
        ))
    
    return result


@app.get("/api/memories")
async def get_memories(
    authorization: str = Header(..., alias="Authorization"),
    limit: int = Query(50, ge=1, le=200)
) -> List[DiaryEntryResponse]:
    """
    Get conversation memories (diary entries of type 'conversation_memory').
    
    Headers:
        Authorization: Telegram WebApp init data
        
    Query Parameters:
        limit: Number of memories to return (1-200)
    """
    init_data = authorization.replace("Bearer ", "")
    telegram_id = get_user_from_init_data(init_data)
    
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user['id']
    
    # Get all diary entries
    diary_entries = db.get_diary_entries(user_id, limit=limit * 2)
    
    # Filter for conversation memories
    memories = [
        entry for entry in diary_entries 
        if entry.entry_type == 'conversation_memory'
    ][:limit]
    
    # Convert to response format
    result = []
    for entry in memories:
        result.append(DiaryEntryResponse(
            id=entry.id,
            entry_type=entry.entry_type,
            title=entry.title,
            content=entry.content,
            importance=entry.importance,
            timestamp=entry.timestamp.isoformat(),
            exchange_start=entry.exchange_start.isoformat() if entry.exchange_start else None,
            exchange_end=entry.exchange_end.isoformat() if entry.exchange_end else None
        ))
    
    return result


@app.get("/api/diary")
async def get_diary_entries(
    authorization: str = Header(..., alias="Authorization"),
    limit: int = Query(50, ge=1, le=200),
    entry_type: Optional[str] = Query(None)
) -> List[DiaryEntryResponse]:
    """
    Get all diary entries (milestones, achievements, etc.).
    
    Headers:
        Authorization: Telegram WebApp init data
        
    Query Parameters:
        limit: Number of entries to return (1-200)
        entry_type: Filter by entry type (optional)
    """
    init_data = authorization.replace("Bearer ", "")
    telegram_id = get_user_from_init_data(init_data)
    
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user['id']
    
    # Get diary entries
    diary_entries = db.get_diary_entries(user_id, limit=limit)
    
    # Filter by type if specified
    if entry_type:
        diary_entries = [e for e in diary_entries if e.entry_type == entry_type]
    
    # Convert to response format
    result = []
    for entry in diary_entries:
        result.append(DiaryEntryResponse(
            id=entry.id,
            entry_type=entry.entry_type,
            title=entry.title,
            content=entry.content,
            importance=entry.importance,
            timestamp=entry.timestamp.isoformat(),
            exchange_start=entry.exchange_start.isoformat() if entry.exchange_start else None,
            exchange_end=entry.exchange_end.isoformat() if entry.exchange_end else None
        ))
    
    return result


@app.get("/api/timeline")
async def get_timeline(
    authorization: str = Header(..., alias="Authorization"),
    days: int = Query(30, ge=1, le=365)
) -> List[MemoryTimeline]:
    """
    Get activity timeline grouped by day.
    
    Headers:
        Authorization: Telegram WebApp init data
        
    Query Parameters:
        days: Number of days to include (1-365)
    """
    init_data = authorization.replace("Bearer ", "")
    telegram_id = get_user_from_init_data(init_data)
    
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user['id']
    
    # Get all data
    conversations = db.get_recent_conversations(user_id, limit=10000)
    diary_entries = db.get_diary_entries(user_id, limit=10000)
    
    # Group by date
    timeline_data = {}
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Process conversations
    for conv in conversations:
        if conv.timestamp < cutoff_date:
            continue
        date_key = conv.timestamp.date().isoformat()
        if date_key not in timeline_data:
            timeline_data[date_key] = {
                'conversations': 0,
                'memories': 0,
                'diary_entries': 0
            }
        timeline_data[date_key]['conversations'] += 1
    
    # Process diary entries
    for entry in diary_entries:
        if entry.timestamp < cutoff_date:
            continue
        date_key = entry.timestamp.date().isoformat()
        if date_key not in timeline_data:
            timeline_data[date_key] = {
                'conversations': 0,
                'memories': 0,
                'diary_entries': 0
            }
        
        if entry.entry_type == 'conversation_memory':
            timeline_data[date_key]['memories'] += 1
        else:
            timeline_data[date_key]['diary_entries'] += 1
    
    # Convert to list and sort
    result = [
        MemoryTimeline(
            date=date,
            conversations=data['conversations'],
            memories=data['memories'],
            diary_entries=data['diary_entries']
        )
        for date, data in timeline_data.items()
    ]
    
    result.sort(key=lambda x: x.date, reverse=True)
    
    return result


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Made with Bob
