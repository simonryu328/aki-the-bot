# AI Companion

A personal AI agent that runs locally and proactively cares for the user. It sends thoughtful messages throughout the day, remembers conversations, understands images, and genuinely wants to help the user succeed.

## Features (Planned)

- 💬 **Conversational AI**: Chat naturally with an AI that remembers context
- 🖼️ **Vision Understanding**: Send photos and the AI understands them
- 📔 **Personal Diary**: AI maintains a diary of your milestone moments
- ⏰ **Proactive Messaging**: AI reaches out at the right times (good morning, reminders, check-ins)
- 🧠 **Long-term Memory**: Remembers facts about you, upcoming events, goals
- 🎯 **Caring Support**: Genuinely curious and supportive of your life

## Tech Stack

- **Backend**: Python 3.11+
- **Bot Platform**: Telegram (via python-telegram-bot)
- **LLM**: OpenAI GPT-4 & GPT-4 Vision
- **Database**: PostgreSQL (structured data) + ChromaDB (vector embeddings)
- **Scheduler**: APScheduler (proactive messages)
- **Package Manager**: uv

## Project Structure

```
ai-companion/
├── bot/                    # Telegram bot handlers
├── agents/                 # AI agents (conversational, proactive, curator)
├── memory/                 # Memory management (database + vector store)
├── scheduler/              # Scheduling system for proactive messages
├── utils/                  # Utilities (OpenAI client, prompts, etc.)
├── config/                 # Configuration and settings
├── main.py                 # Entry point
└── pyproject.toml          # Dependencies
```

## Setup Instructions

### 1. Prerequisites

- Python 3.11 or higher
- PostgreSQL database
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- OpenAI API Key

### 2. Installation

```bash
# Install uv if not already installed
pip install uv

# Clone/navigate to project directory
cd ai-companion

# Install dependencies
uv sync
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env and fill in your credentials:
# - TELEGRAM_BOT_TOKEN (from BotFather)
# - OPENAI_API_KEY (from OpenAI)
# - DATABASE_URL (PostgreSQL connection string)
```

### 4. Database Setup

```bash
# Create PostgreSQL database
createdb ai_companion

# Migrations will be added in Phase 2
```

### 5. Run the Bot

```bash
# Using uv
uv run main.py

# Or activate venv and run directly
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python main.py
```

## Getting Your Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow prompts to name your bot
4. Copy the token provided
5. Add to your `.env` file

## Development Phases

### ✅ Phase 1: Project Foundation & Basic Bot
- [x] Project structure created
- [x] uv package management configured
- [x] Telegram bot receives and acknowledges messages
- [x] Handles text messages and images (basic)

### 🔄 Phase 2: Memory System (In Progress)
- [ ] PostgreSQL schema for user data
- [ ] ChromaDB setup for semantic search
- [ ] Memory manager interface

### ⏳ Phase 3: Conversational Agent
- [ ] OpenAI integration
- [ ] Context-aware responses
- [ ] Memory retrieval during conversations

### ⏳ Phase 4: Vision Processor
- [ ] GPT-4 Vision integration
- [ ] Image understanding and analysis
- [ ] Milestone detection from images

### ⏳ Phase 5: Memory Curator
- [ ] Automatic fact extraction
- [ ] Timeline event detection
- [ ] Diary entry creation

### ⏳ Phase 6: Proactive Agent & Scheduler
- [ ] APScheduler setup
- [ ] Proactive message triggers
- [ ] Smart timing decisions

### ⏳ Phase 7: Frontend Dashboard
- [ ] TypeScript + Vite setup
- [ ] Conversation viewer
- [ ] Memory browser
- [ ] Settings panel

## Usage (After Phase 3+)

1. Start a chat with your bot on Telegram
2. Send `/start` to begin
3. Chat naturally - the AI remembers everything
4. Send photos - the AI understands them
5. The AI will proactively reach out to you throughout the day

## Development

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run the bot
python main.py

# View logs
# Logs are output to console (configured in bot/telegram_handler.py)
```

## License

MIT
