# AI Companion - Implementation Plan

## Project Overview

A personal AI agent that runs locally and proactively cares for the user. It sends thoughtful messages throughout the day, remembers conversations, understands images, and genuinely wants to help the user succeed.

### Core Principles
- **Deeply caring**: The AI genuinely cares about the user's wellbeing and success
- **Proactively curious**: Continuously asks questions to understand the user better
- **Context-aware**: Remembers everything and uses it naturally
- **Milestone tracking**: Maintains a diary of important moments
- **Vision-enabled**: Understands images the user shares

### Tech Stack Decisions
- **Language**: Python 3.11+
- **Package Manager**: uv (fast, modern)
- **Bot Platform**: Telegram (python-telegram-bot library)
- **LLM**: OpenAI GPT-4 (text) + GPT-4 Vision (images)
- **Database**: PostgreSQL (structured data)
- **Vector DB**: ChromaDB (semantic search, local mode)
- **Scheduler**: APScheduler (proactive messaging)
- **Frontend**: TypeScript + Vite + React (Phase 7)

---

## AI Engineering Architecture

### Agent Roles

1. **Conversational Agent** (Reactive)
   - Responds to user messages
   - Asks curious, caring follow-up questions
   - Identifies important information to remember

2. **Proactive Agent** (Initiating)
   - Knows current time/date
   - Reviews user's context to decide when to reach out
   - Generates contextually relevant messages

3. **Memory Curator** (Reflection/Storage)
   - Processes conversations to extract facts
   - Identifies milestone moments
   - Organizes memories by importance/recency/topic
   - Updates user profile continuously

4. **Vision Processor** (Image Understanding)
   - Analyzes images with VLM (GPT-4 Vision)
   - Extracts semantic meaning and emotional tone
   - Determines if image represents a milestone
   - Generates descriptive memory entries

### Memory Architecture (Hierarchical)

```
User Memory Store
├── Profile (Who they are)
│   ├── Basic facts (name, location, job)
│   ├── Preferences (likes/dislikes)
│   └── Relationships (people in their life)
│
├── Timeline (What's happening)
│   ├── Upcoming events (meetings, trips)
│   ├── Recurring patterns (gym Tuesdays)
│   └── Goals & aspirations
│
├── Diary (Milestone moments)
│   ├── Achievements (promotions, accomplishments)
│   ├── Significant events (weddings, births)
│   ├── Emotional milestones (breakthroughs, challenges)
│   └── Visual memories (images with VLM descriptions)
│
└── Conversation History
    ├── Recent exchanges (last 7 days, high detail)
    ├── Older conversations (summarized)
    └── Semantic clusters (topics discussed)
```

### Context Assembly Strategy

For each interaction, the agent assembles:
1. System Prompt (personality, role, behavior rules)
2. User Profile Summary (who they are - ~200 tokens)
3. Relevant Timeline Items (upcoming events - ~100 tokens)
4. Retrieved Memories (semantic search - ~500 tokens)
5. Recent Conversation (last 5-10 messages - ~800 tokens)
6. Current Time/Date Context
7. [If image sent] VLM analysis of image

**Retrieval Strategy:**
- Semantic similarity search (user message → relevant memories)
- Time-based filtering (upcoming events, recent milestones)
- Importance weighting (milestone > casual fact)

### Proactive Messaging Decision System

**Trigger System Architecture:**
```
┌─────────────────────────────────────────────┐
│   Trigger System (Orchestrator)             │
├─────────────────────────────────────────────┤
│                                             │
│  1. Fixed Schedule Triggers                 │
│     • Morning (8am)                         │
│     • Evening (8pm if no contact)           │
│     • Event reminders (from calendar)       │
│                                             │
│  2. Intent Queue (AI-scheduled)             │
│     • Follow-ups from conversations         │
│     • Milestone check-ins                   │
│     • Goal tracking                         │
│                                             │
│  3. Spontaneous Evaluation (2-3x daily)     │
│     • AI evaluates: "Should I reach out?"   │
│     • Only if conditions met                │
│                                             │
└─────────────────────────────────────────────┘
```

**Key Principles:**
- Be deterministic where possible (morning messages, event reminders)
- Let AI schedule proactively during conversations (intent queue)
- Minimize expensive evaluations (only 2-3 spontaneous checks/day)
- Always respect user preferences (quiet hours, frequency limits)

---

## Implementation Phases

### ✅ Phase 1: Project Foundation & Basic Telegram Bot

**Status**: COMPLETED

**What was built:**
- [x] Project structure with proper directories
- [x] uv package management configured
- [x] All dependencies installed (python-telegram-bot, openai, psycopg2-binary, sqlalchemy, chromadb, apscheduler)
- [x] Configuration system (config/settings.py) with environment variable loading
- [x] Basic Telegram bot (bot/telegram_handler.py)
  - Handles `/start` command with welcoming message
  - Receives and acknowledges text messages
  - Receives and acknowledges photos
  - Logging configured
- [x] Entry point (main.py) to run the bot
- [x] Documentation (README.md)
- [x] .env.example template

**Files created:**
- `main.py` - Entry point
- `bot/telegram_handler.py` - Telegram bot handler
- `config/settings.py` - Configuration management
- `.env.example` - Environment template
- `pyproject.toml` - Dependencies
- `README.md` - Documentation

**Database setup:**
- PostgreSQL running in Docker container
- Connection string: `postgresql://postgres:yourpassword@localhost:5432/ai_companion`

**Testing Phase 1:**
```bash
uv run main.py
# Then message the bot on Telegram
```

---

### 🔄 Phase 2: Memory System (PostgreSQL + ChromaDB)

**Status**: IN PROGRESS

**Goal**: Build the storage layer for all user memories

**Detailed steps:**

1. **Design and implement database schema** (PostgreSQL)
   ```sql
   Tables:
   - users (id, telegram_id, name, username, created_at, last_interaction)
   - profile_facts (user_id, category, key, value, confidence, updated_at)
   - timeline_events (user_id, event_type, title, description, datetime, reminded, created_at)
   - diary_entries (user_id, entry_type, title, content, importance, image_url, timestamp)
   - conversations (user_id, role, message, timestamp)
   - scheduled_messages (user_id, scheduled_time, message_type, context, executed, created_at)
   ```

2. **Build database.py**
   - SQLAlchemy models for all tables
   - Engine and session management
   - CRUD operations for each table
   - Helper methods:
     - `get_or_create_user(telegram_id, name, username)`
     - `get_user_profile(user_id)` - returns all profile facts
     - `add_timeline_event(user_id, event_type, title, description, datetime)`
     - `get_upcoming_events(user_id, days=7)`
     - `add_diary_entry(user_id, entry_type, title, content, importance, image_url)`
     - `add_conversation(user_id, role, message)`
     - `get_recent_conversations(user_id, limit=10)`

3. **Build vector_store.py** (ChromaDB)
   - Initialize ChromaDB collection with persistence
   - `add_memory(user_id, text, metadata)` - embed and store conversation chunks
   - `search_memories(user_id, query, k=5)` - semantic search for relevant memories
   - Metadata structure: `{user_id, timestamp, message_type, importance}`

4. **Build memory_manager.py**
   - Unified interface to both database and vector store
   - `get_user_context(user_id)` - returns:
     - User profile summary
     - Recent conversations
     - Upcoming timeline events
   - `search_relevant_memories(user_id, query, k=5)` - semantic search
   - `add_conversation(user_id, role, message)` - stores in both DB and vector store
   - `add_profile_fact(user_id, category, key, value)`
   - `add_timeline_event(...)`
   - `add_diary_entry(...)`

5. **Create database initialization script**
   - `scripts/init_db.py` - creates all tables
   - Run once to set up schema

6. **Testing Phase 2:**
   - Create test script that:
     - Adds a test user
     - Stores some profile facts
     - Adds conversations
     - Performs semantic search
     - Retrieves user context

**Files to create:**
- `memory/models.py` - SQLAlchemy models
- `memory/database.py` - Database operations
- `memory/vector_store.py` - ChromaDB interface
- `memory/memory_manager.py` - Unified memory interface
- `scripts/init_db.py` - Database initialization

---

### ⏳ Phase 3: Conversational Agent with Memory

**Goal**: AI responds intelligently with full context awareness

**Detailed steps:**

1. **Build prompts.py** - All prompts in one place
   ```python
   SYSTEM_PROMPT = """
   You are a caring AI companion who deeply values your relationship with {user_name}.

   Core principles:
   - You are genuinely curious about their life and experiences
   - You remember what they share and reference it naturally
   - You celebrate their wins and support them through challenges
   - You ask thoughtful follow-up questions to understand them better
   - You help them succeed by being supportive and caring

   Current context:
   - Today is {current_datetime}
   - Recent conversation: {recent_messages}
   - Known facts: {profile_summary}
   - Upcoming events: {timeline_items}

   When user shares something important, acknowledge it and ask caring follow-ups.
   """
   ```

2. **Build openai_client.py**
   - Wrapper for OpenAI API calls
   - `chat_completion(messages, model="gpt-4o")`
   - `create_embedding(text)` - for vector store
   - Error handling and retries
   - Token usage logging

3. **Build conversational_agent.py**
   - `ConversationalAgent` class
   - `respond(user_id, user_message)` method:
     1. Get user from database (or create)
     2. Get user context from memory manager (profile + timeline)
     3. Search for relevant memories (semantic)
     4. Get recent conversation history
     5. Assemble system prompt with all context
     6. Call OpenAI with assembled context
     7. Return response

4. **Integrate into telegram_handler.py**
   - Replace echo logic in `handle_text_message()`
   - Call conversational agent
   - Store conversation in memory
   - Send agent's response

5. **Testing Phase 3:**
   - Have multi-turn conversation
   - Verify bot references previous messages
   - Check that context is being used

**Files to create:**
- `utils/prompts.py` - Prompt templates
- `utils/openai_client.py` - OpenAI wrapper
- `agents/conversational_agent.py` - Main conversational logic

**Files to modify:**
- `bot/telegram_handler.py` - Integrate conversational agent

---

### ⏳ Phase 4: Vision Processor for Images

**Goal**: Bot understands images and extracts meaning

**Detailed steps:**

1. **Build vision_processor.py**
   - `VisionProcessor` class
   - `analyze_image(image_url, user_context)` method:
     - Download image from Telegram
     - Call OpenAI Vision API with prompt:
       ```
       You are analyzing a photo shared by {user_name}.

       Context about the user:
       {user_context_summary}

       Analyze this image:
       1. Describe what you see in detail
       2. Identify emotional tone (celebratory, casual, sad, excited, etc.)
       3. Note any people, places, or significant elements
       4. Assess significance: Is this a milestone moment? Rate 0-10
       5. Suggest caring follow-up questions to ask the user

       Return structured analysis.
       ```
     - Parse and return structured response

2. **Update telegram_handler.py**
   - In `handle_photo_message()`:
     - Download image from Telegram
     - Get user context
     - Call vision processor
     - If milestone (score > 7): add to diary
     - Store image analysis in memory
     - Have conversational agent respond about the image with follow-up questions

3. **Update memory system**
   - Add image storage (save to local directory or S3)
   - Link diary entries to image files
   - Store image descriptions in vector store for semantic search

4. **Testing Phase 4:**
   - Send various types of images:
     - Milestone moment (graduation, achievement)
     - Casual photo (food, scenery)
     - Photo with people
   - Verify bot understands and responds appropriately
   - Check diary entries are created for milestones

**Files to create:**
- `agents/vision_processor.py` - Image analysis

**Files to modify:**
- `bot/telegram_handler.py` - Image handling
- `memory/memory_manager.py` - Image storage

---

### ⏳ Phase 5: Memory Curator (Auto-Extract Facts)

**Goal**: Automatically extract and store important information

**Detailed steps:**

1. **Build memory_curator.py**
   - `MemoryCurator` class
   - `process_conversation(user_id, conversation_messages)` method:
     - Call OpenAI with extraction prompt:
       ```
       Analyze this conversation and extract:

       1. NEW FACTS about the user:
          - Basic info (job, location, age, etc.)
          - Preferences (likes, dislikes, habits)
          - Relationships (people mentioned, their roles)

       2. UPCOMING EVENTS:
          - Extract any events with dates/times
          - Format: {title, description, datetime}

       3. GOALS OR CHALLENGES:
          - Things user wants to achieve
          - Problems they're working on

       4. MILESTONE MOMENTS:
          - Significant events or achievements
          - Rate importance 0-10

       Return structured JSON.
       ```
     - Parse response
     - Update database:
       - Add/update profile facts
       - Create timeline events
       - Create diary entries for milestones
       - Schedule follow-up messages in intent queue

2. **Integrate into conversation flow**
   - After each conversation turn (or every N turns), trigger curator
   - Run asynchronously to not block responses
   - Log what was extracted for debugging

3. **Build memory review tools**
   - `scripts/view_memories.py` - CLI to view all stored data for a user
   - Useful for debugging and verifying extraction

4. **Testing Phase 5:**
   - Have conversation mentioning:
     - A new fact ("I work as a software engineer")
     - An upcoming event ("I have a dentist appointment Tuesday at 2pm")
     - A goal ("I'm trying to exercise more")
   - Check database to verify all were extracted and stored correctly

**Files to create:**
- `agents/memory_curator.py` - Fact extraction
- `scripts/view_memories.py` - Debug tool

**Files to modify:**
- `bot/telegram_handler.py` - Trigger curator after conversations

---

### ⏳ Phase 6: Scheduler & Proactive Agent

**Goal**: Bot initiates messages at the right times

**Detailed steps:**

1. **Build triggers.py** - Define trigger schedule
   ```python
   TRIGGERS = {
       "morning_message": {
           "time": "08:00",
           "frequency": "daily",
           "condition": "if_no_interaction_in_last_12_hours"
       },
       "evening_checkin": {
           "time": "20:00",
           "frequency": "daily",
           "condition": "if_no_interaction_today"
       },
       "spontaneous_check": {
           "times": ["12:00", "17:00"],
           "frequency": "daily",
           "condition": "ai_evaluation_required"
       }
   }
   ```

2. **Build proactive_agent.py**
   - `ProactiveAgent` class
   - `should_reach_out(user_id, trigger_type)` method:
     - Get user context
     - Get last interaction time
     - Call OpenAI with decision prompt:
       ```
       Current time: {now}
       User: {user_name}
       Last interaction: {X hours ago}
       Recent topics: {summary}
       Upcoming events: {events}

       Should you reach out now?
       Consider:
       - Is the timing appropriate?
       - Is there something meaningful to say?
       - Have you messaged too recently?

       Respond: YES (with message) or NO (with reason)
       ```
     - Return (should_send, message)

   - `generate_morning_message(user_id)` - contextual good morning
   - `generate_event_reminder(user_id, event)` - supportive reminder
   - `check_intent_queue(user_id)` - execute scheduled follow-ups

3. **Build scheduler.py**
   - Initialize APScheduler with BackgroundScheduler
   - Register all triggers from triggers.py
   - Each trigger:
     - Queries all active users
     - Calls proactive agent for each user
     - Sends message if agent decides to
   - Start scheduler in background thread

4. **Add intent queue to database** (already in schema)
   - During conversations, curator adds scheduled follow-ups:
     - "User mentioned job interview Thursday → schedule supportive message Thursday morning"
     - "User set exercise goal → schedule check-in 3 days from now"

5. **Integrate into main.py**
   - Start scheduler alongside bot
   - Graceful shutdown handling

6. **Testing Phase 6:**
   - Trigger a morning message manually (change time to current time)
   - Mention an event in conversation ("I have a meeting at 3pm")
   - Wait for event reminder
   - Verify intent queue creates follow-ups

**Files to create:**
- `scheduler/triggers.py` - Trigger definitions
- `agents/proactive_agent.py` - Proactive messaging logic
- `scheduler/scheduler.py` - APScheduler setup

**Files to modify:**
- `main.py` - Start scheduler
- `agents/memory_curator.py` - Add to intent queue

---

### ⏳ Phase 7: Frontend Dashboard (TypeScript + Vite)

**Goal**: Web interface to view and manage the AI companion

**Detailed steps:**

1. **Set up FastAPI backend** (Python)
   - Create `api/` directory
   - Build REST API endpoints:
     - `GET /api/users/{user_id}/conversations` - chat history
     - `GET /api/users/{user_id}/profile` - stored facts
     - `GET /api/users/{user_id}/diary` - milestone moments
     - `GET /api/users/{user_id}/timeline` - upcoming events
     - `GET /api/users/{user_id}/scheduled` - intent queue
     - `PUT /api/users/{user_id}/settings` - update preferences
   - CORS configuration
   - Run on separate port (8000)

2. **Create frontend/** directory
   - `npm create vite@latest frontend -- --template react-ts`
   - Install dependencies:
     - React Router
     - TanStack Query (data fetching)
     - Tailwind CSS (styling)
     - Recharts (analytics)

3. **Build React components**
   - `ConversationViewer` - Timeline of messages
   - `MemoryBrowser` - View all stored profile facts
   - `DiaryTimeline` - Milestone moments with images
   - `EventCalendar` - Upcoming timeline events
   - `ScheduledMessages` - Intent queue viewer
   - `SettingsPanel` - Configure quiet hours, frequency, etc.
   - `Dashboard` - Overview with stats

4. **Styling and polish**
   - Responsive design
   - Dark mode
   - Loading states
   - Error handling

5. **Testing Phase 7:**
   - View real data from database
   - Update settings and verify they apply
   - Browse memories and verify accuracy

**Files to create:**
- `api/main.py` - FastAPI app
- `api/routes/` - API endpoints
- `frontend/` - Entire React app

---

## Current Status Summary

**Completed:**
- ✅ Phase 1: Basic bot working, can receive messages and images

**In Progress:**
- 🔄 Phase 2: Building memory system next

**Not Started:**
- ⏳ Phases 3-7

**Infrastructure:**
- PostgreSQL: Running in Docker
- ChromaDB: Will use local persistence (no setup needed)
- Telegram Bot: Created and configured

---

## Critical Implementation Notes

### Database Migrations
- Use SQLAlchemy's `create_all()` for initial setup
- For production, consider Alembic for migrations

### Error Handling
- All OpenAI calls should have retry logic
- Database operations should handle connection failures
- Telegram bot should handle rate limits

### Privacy & Data Management
- All data stored locally (PostgreSQL + ChromaDB)
- User can delete their data (add endpoint in Phase 7)
- Consider data retention policies

### Cost Management
- GPT-4 API calls can be expensive
- Use GPT-4o-mini for less critical tasks (summarization, extraction)
- Use GPT-4o for main conversation and vision
- Monitor token usage

### Testing Strategy
- Unit tests for core logic (memory manager, agents)
- Integration tests for database operations
- End-to-end test: full conversation flow
- Manual testing on Telegram throughout

---

## Next Steps

**Immediate (Phase 2):**
1. Create database schema and models
2. Implement database operations
3. Set up ChromaDB
4. Build memory manager interface
5. Test memory storage and retrieval

**After Phase 2:**
- Proceed to Phase 3 (Conversational Agent)
- Then Phase 4 (Vision)
- Then Phase 5 (Memory Curator)
- Then Phase 6 (Proactive Agent)
- Finally Phase 7 (Frontend Dashboard)

---

## Environment Setup Reference

```bash
# .env file structure
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/ai_companion
CHROMA_PERSIST_DIRECTORY=./chroma_data
LOG_LEVEL=INFO
TIMEZONE=America/Toronto
```

```bash
# Running the bot
uv run main.py

# Database initialization (Phase 2)
uv run scripts/init_db.py

# View user memories (Phase 5+)
uv run scripts/view_memories.py --user-id 1
```

---

## Key Design Decisions Made

1. **Why pure Python instead of LangGraph?**
   - Simpler to understand and debug
   - Full control over agent logic
   - No framework overhead
   - Easier to customize

2. **Why Telegram?**
   - Easy to set up
   - Free
   - Rich media support (images, documents)
   - User already familiar with the app

3. **Why PostgreSQL + ChromaDB?**
   - PostgreSQL: Reliable, structured data storage
   - ChromaDB: Fast semantic search, works locally
   - Hybrid approach: best of both worlds

4. **Why OpenAI instead of local LLM?**
   - Higher quality responses
   - Better vision capabilities (GPT-4 Vision)
   - Easier to start (can switch to local later)
   - User accepted cloud-based approach

5. **Proactive messaging strategy:**
   - Hybrid: fixed triggers + AI-scheduled + spontaneous
   - Avoids spam by limiting spontaneous checks to 2-3x daily
   - Intent queue allows AI to plan ahead during conversations

---

*This document serves as the complete project plan and can be used to resume development in a new chat session if context limits are reached.*
