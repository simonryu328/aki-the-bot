# Phase 2: Production-Grade Memory System

## Overview

Phase 2 has been rebuilt from the ground up with production-grade architecture and scalability in mind. This is not an MVP - this is a production-ready, enterprise-grade memory system.

## Architecture

### Core Principles

1. **Type Safety**: Pydantic schemas throughout for compile-time safety
2. **Async Everything**: Non-blocking I/O for maximum performance
3. **Graceful Degradation**: System works even if components fail
4. **Observability**: Structured logging for production debugging
5. **Resilience**: Retry logic with exponential backoff
6. **Clean Architecture**: Separation of concerns, dependency injection

## Technology Stack

### Dependencies

```toml
dependencies = [
    "python-telegram-bot>=21.0",      # Telegram Bot API
    "openai>=1.50.0",                 # LLM and embeddings
    "python-dotenv>=1.0.0",           # Environment management
    "sqlalchemy[asyncio]>=2.0.0",     # Async ORM
    "asyncpg>=0.29.0",                # Async PostgreSQL driver
    "pydantic>=2.5.0",                # Data validation
    "pydantic-settings>=2.1.0",       # Configuration management
    "pinecone>=5.0.0",                # Vector database
    "apscheduler>=3.10.4",            # Task scheduling
    "structlog>=24.1.0",              # Structured logging
    "tenacity>=8.2.3",                # Retry logic
]
```

## Component Architecture

### 1. Pydantic Schemas (`schemas/`)

Type-safe data transfer objects for all entities:

**Features:**
- Automatic validation
- Clear separation: Create/Update/Read schemas
- Bidirectional ORM conversion (`from_attributes=True`)
- Business logic methods (e.g., `UserContextSchema.to_prompt_context()`)

**Files:**
- `user.py` - User data models
- `profile.py` - Profile facts
- `conversation.py` - Chat messages
- `timeline.py` - Calendar events
- `diary.py` - Milestone memories
- `scheduled_message.py` - Proactive messaging
- `context.py` - Complete user context for AI

**Example:**
```python
from schemas import UserSchema, UserContextSchema

# Type-safe user data
user: UserSchema = await memory_manager.get_or_create_user(
    telegram_id=12345,
    name="Simon",
    username="simon"
)

# Complete AI context with prompt generation
context: UserContextSchema = await memory_manager.get_user_context(user.id)
prompt = context.to_prompt_context()  # Ready for LLM
```

### 2. Async Database (`memory/database_async.py`)

Production-grade PostgreSQL interface:

**Features:**
- Async SQLAlchemy with connection pooling
- Retry logic (3 attempts, exponential backoff)
- Returns Pydantic models (type-safe)
- Context managers for transaction safety
- Connection health checks (`pool_pre_ping`)
- Connection recycling (1 hour)

**Configuration:**
```python
engine = create_async_engine(
    db_url,
    pool_size=10,           # Max connections
    max_overflow=20,        # Additional connections under load
    pool_pre_ping=True,     # Check connection health
    pool_recycle=3600,      # Recycle after 1 hour
)
```

**Example:**
```python
from memory.database_async import db

# Automatic retry on transient failures
user = await db.get_or_create_user(telegram_id=12345)

# Type-safe results
conversations: List[ConversationSchema] = await db.get_recent_conversations(
    user_id=user.id,
    limit=10
)
```

### 3. Exception Hierarchy (`core/exceptions.py`)

Structured error handling:

**Exception Classes:**
- `AICompanionException` - Base exception
- `DatabaseException` - Database errors
  - `RecordNotFoundError`
  - `DuplicateRecordError`
  - `DatabaseConnectionError`
- `VectorStoreException` - Vector store errors
  - `VectorStoreConnectionError`
  - `EmbeddingError`
- `MemoryException` - Memory operations
  - `UserNotFoundError`
  - `InvalidMemoryDataError`
- `ExternalServiceException` - API errors
  - `OpenAIAPIError`
  - `TelegramAPIError`
- `ValidationException` - Input validation
  - `InvalidInputError`
  - `ConfigurationError`

**Features:**
- Machine-readable error codes
- Structured context
- Serializable to JSON
- Easy to log and monitor

**Example:**
```python
from core import UserNotFoundError, DatabaseException

try:
    user = await memory_manager.get_user_by_id(999)
    if not user:
        raise UserNotFoundError(user_id=999)
except DatabaseException as e:
    logger.error("Database error", **e.to_dict())
    # {
    #   "error": "USER_NOT_FOUND",
    #   "message": "User 999 not found",
    #   "context": {"user_id": 999}
    # }
```

### 4. Structured Logging (`core/logging_config.py`)

Production-ready observability:

**Features:**
- JSON output for log aggregation
- Context-rich logging
- Automatic timestamps (ISO format)
- Stack traces for exceptions
- Easy integration with monitoring tools

**Example:**
```python
from core import configure_logging, get_logger

configure_logging(log_level="INFO")
logger = get_logger(__name__)

logger.info(
    "User created",
    user_id=user.id,
    telegram_id=telegram_id,
    duration_ms=42
)
# Output:
# {
#   "event": "User created",
#   "level": "info",
#   "timestamp": "2026-02-03T12:34:56.789Z",
#   "user_id": 1,
#   "telegram_id": 12345,
#   "duration_ms": 42,
#   "app": "ai-companion"
# }
```

### 5. Vector Store (`memory/vector_store.py`)

Production-grade Pinecone integration:

**Features:**
- Retry logic with exponential backoff
- Automatic text truncation
- Graceful degradation
- Namespace isolation per user
- Rate limiting friendly

**Example:**
```python
from memory.vector_store import vector_store

# Automatic retry on transient failures
memory_id = vector_store.add_memory(
    user_id=1,
    text="User prefers React over Vue",
    metadata={"category": "preferences"}
)

# Semantic search
results = vector_store.search_memories(
    user_id=1,
    query="What frontend frameworks does user like?",
    k=5
)
```

### 6. Pydantic Settings (`config/settings.py`)

Type-safe configuration:

**Features:**
- Automatic .env loading
- Type validation
- Clear error messages
- Environment-aware (dev/staging/prod)
- Field-level validation

**Example:**
```python
from config.settings import settings

# Type-safe access
db_url: str = settings.DATABASE_URL
is_prod: bool = settings.is_production

# Automatic validation on startup
# ValueError: DATABASE_URL must start with postgresql://
```

### 7. Async Memory Manager (`memory/memory_manager_async.py`)

Unified interface combining all components:

**Features:**
- Type-safe operations
- Graceful degradation
- Comprehensive error handling
- Async/await for performance

**Example:**
```python
from memory.memory_manager_async import memory_manager

# Complete type-safe workflow
user = await memory_manager.get_or_create_user(12345, "Simon")
await memory_manager.add_profile_fact(user.id, "basic_info", "job", "Engineer")
await memory_manager.add_conversation(user.id, "user", "Hello!")

context = await memory_manager.get_user_context(user.id)
# context: UserContextSchema
```

## Database Schema

### Tables

1. **users** - Telegram user information
2. **profile_facts** - User profile data (categorized)
3. **conversations** - Chat history
4. **timeline_events** - Calendar events
5. **diary_entries** - Milestone moments
6. **scheduled_messages** - Proactive messaging queue

See `memory/models.py` for complete schema.

## Usage

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in values:

```bash
TELEGRAM_BOT_TOKEN=your_token_here
OPENAI_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here  # Optional
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_companion
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### 3. Initialize Database

```bash
uv run scripts/init_db_async.py
```

### 4. Run Tests

```bash
uv run scripts/test_memory_async.py
```

## Performance Characteristics

### Async Benefits

- **Non-blocking I/O**: Handle 1000s of concurrent operations
- **Connection pooling**: Efficient database usage
- **Parallel operations**: Fetch profile + conversations + events simultaneously

### Scalability

- **Horizontal scaling**: Stateless design, can run multiple instances
- **Database connection pooling**: 10 base + 20 overflow connections
- **Vector store namespaces**: Per-user isolation
- **Retry logic**: Handles transient failures gracefully

### Monitoring

- **Structured logs**: Easy to aggregate and analyze
- **Error tracking**: Exception context for debugging
- **Performance metrics**: Duration logging throughout

## Error Handling Strategy

### 1. Database Errors

- Retry 3x with exponential backoff
- Log with full context
- Raise typed exceptions

### 2. Vector Store Errors

- Retry 3x with exponential backoff
- Graceful degradation (system works without it)
- Log warnings, don't fail operations

### 3. External API Errors

- Retry with backoff
- Log with status codes and details
- Raise typed exceptions for handling

## Production Deployment Checklist

- [ ] Set `ENVIRONMENT=production` in .env
- [ ] Configure log aggregation (Datadog, CloudWatch, etc.)
- [ ] Set up error tracking (Sentry, Rollbar, etc.)
- [ ] Configure database connection pooling for load
- [ ] Enable database read replicas if needed
- [ ] Set up monitoring dashboards
- [ ] Configure alerts for error rates
- [ ] Set up backup strategy for PostgreSQL
- [ ] Review and tune retry configurations
- [ ] Load test with expected traffic

## Future Enhancements

### Phase 3 Integration

The memory system is ready for Phase 3 (Conversational Agent):

```python
from memory.memory_manager_async import memory_manager

async def handle_message(telegram_id: int, message: str):
    # Get user
    user = await memory_manager.get_or_create_user(telegram_id)

    # Get context
    context = await memory_manager.get_user_context(user.id)

    # Generate response (Phase 3)
    response = await ai_agent.generate_response(
        message=message,
        context=context.to_prompt_context()
    )

    # Store conversation
    await memory_manager.add_conversation(user.id, "user", message)
    await memory_manager.add_conversation(user.id, "assistant", response)

    return response
```

### Observability Improvements

- Metrics (Prometheus/StatsD)
- Distributed tracing (OpenTelemetry)
- APM integration (New Relic, Datadog APM)

### Performance Optimizations

- Redis caching layer
- Read replicas for database
- CDN for static assets (Phase 7)

## Comparison: MVP vs Production

| Feature | MVP Approach | Production Approach |
|---------|-------------|---------------------|
| **Type Safety** | Dicts | Pydantic schemas |
| **Database** | Sync SQLAlchemy | Async SQLAlchemy with pooling |
| **Error Handling** | Try/catch | Exception hierarchy + retry logic |
| **Logging** | print() / basic logging | Structured JSON logging |
| **Config** | os.getenv() | Pydantic Settings with validation |
| **Vector Store** | Basic wrapper | Retry logic + graceful degradation |
| **Testing** | Manual | Comprehensive async test suite |
| **Scalability** | Single-threaded | Async, horizontal scaling ready |

## Conclusion

Phase 2 is now production-ready with:

✅ Type safety throughout
✅ Async operations for performance
✅ Comprehensive error handling
✅ Structured logging for observability
✅ Retry logic for resilience
✅ Clean architecture for maintainability

This is **not an MVP**. This is a **scalable, production-grade memory system** ready for enterprise deployment.
