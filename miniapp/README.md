# Telegram Mini App - Memory Viewer

A Telegram Mini App that allows users to view their conversation memories, diary entries, and chat history with Aki in a beautiful web interface.

## 🌟 Features

- **📊 Statistics Dashboard**: View total conversations, memories, diary entries, and days active
- **💭 Memories View**: Browse conversation memories with importance ratings
- **💬 Conversations**: Review full chat history with timestamps
- **📔 Diary Entries**: Access all diary entries and milestones
- **📈 Timeline**: See activity over time with daily breakdowns
- **🎨 Telegram Theme Integration**: Automatically adapts to user's Telegram theme
- **🔒 Secure Authentication**: Uses Telegram WebApp signature verification

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Telegram Mini App UI            │
│         (miniapp/index.html)            │
└──────────────┬──────────────────────────┘
               │ HTTPS + Auth Header
               │ (Telegram initData)
┌──────────────▼──────────────────────────┐
│         FastAPI Backend                  │
│         (miniapp/api.py)                 │
│  • Signature verification                │
│  • RESTful API endpoints                 │
│  • CORS for Telegram domains            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      PostgreSQL Database                 │
│      (via memory/database.py)            │
│  • Users, Conversations                  │
│  • Diary Entries, Memories               │
└──────────────────────────────────────────┘
```

## 📋 API Endpoints

### Authentication
All endpoints require the `Authorization` header with Telegram WebApp initData:
```
Authorization: Bearer <telegram_init_data>
```

### Endpoints

#### `GET /api/user/stats`
Get user statistics including total conversations, memories, diary entries, and days active.

**Response:**
```json
{
  "total_conversations": 150,
  "total_diary_entries": 25,
  "total_memories": 15,
  "first_interaction": "2026-01-01T00:00:00",
  "last_interaction": "2026-02-13T23:00:00",
  "days_active": 44
}
```

#### `GET /api/conversations?limit=50&offset=0`
Get conversation history with pagination.

**Query Parameters:**
- `limit` (1-500): Number of messages to return
- `offset` (≥0): Offset for pagination

**Response:**
```json
[
  {
    "role": "user",
    "message": "Hello!",
    "timestamp": "2026-02-13T23:00:00",
    "thinking": null
  },
  {
    "role": "assistant",
    "message": "Hi! How are you?",
    "timestamp": "2026-02-13T23:00:05",
    "thinking": "User seems cheerful..."
  }
]
```

#### `GET /api/memories?limit=50`
Get conversation memories (diary entries of type 'conversation_memory').

**Query Parameters:**
- `limit` (1-200): Number of memories to return

**Response:**
```json
[
  {
    "id": 123,
    "entry_type": "conversation_memory",
    "title": "Discussion about career goals",
    "content": "User shared aspirations to become a software engineer...",
    "importance": 8,
    "timestamp": "2026-02-13T20:00:00",
    "exchange_start": "2026-02-13T19:30:00",
    "exchange_end": "2026-02-13T20:00:00"
  }
]
```

#### `GET /api/diary?limit=50&entry_type=milestone`
Get all diary entries with optional filtering.

**Query Parameters:**
- `limit` (1-200): Number of entries to return
- `entry_type` (optional): Filter by entry type

**Response:** Same format as memories endpoint

#### `GET /api/timeline?days=30`
Get activity timeline grouped by day.

**Query Parameters:**
- `days` (1-365): Number of days to include

**Response:**
```json
[
  {
    "date": "2026-02-13",
    "conversations": 25,
    "memories": 2,
    "diary_entries": 1
  }
]
```

## 🚀 Setup & Deployment

### Local Development

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Set environment variables in `.env`:**
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   OPENAI_API_KEY=your_openai_key
   DATABASE_URL=postgresql://user:pass@localhost:5432/db
   MINIAPP_PORT=8000
   MINIAPP_URL=http://localhost:8000
   ```

3. **Run the API server:**
   ```bash
   uv run python miniapp/run_api.py
   ```

4. **Test locally:**
   - Open `miniapp/index.html` in a browser
   - Or use ngrok to expose localhost: `ngrok http 8000`

### Production Deployment

#### Option 1: Railway (Recommended)

1. **Deploy API server:**
   ```bash
   # Create new Railway project
   railway init
   
   # Set environment variables
   railway variables set MINIAPP_PORT=8000
   railway variables set MINIAPP_URL=https://your-app.up.railway.app
   
   # Deploy
   railway up
   ```

2. **Configure Procfile for API:**
   ```
   web: python miniapp/run_api.py
   ```

3. **Serve static files:**
   - Railway will automatically serve `miniapp/index.html`
   - Or use a separate static hosting service (Vercel, Netlify, etc.)

#### Option 2: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv
RUN uv sync

EXPOSE 8000

CMD ["python", "miniapp/run_api.py"]
```

### Telegram Bot Setup

1. **Create a Web App in BotFather:**
   ```
   /newapp
   Select your bot
   Enter app title: "Memory Viewer"
   Enter description: "View your conversation memories"
   Upload icon (512x512 PNG)
   Enter Web App URL: https://your-miniapp-url.com
   ```

2. **Add menu button command to your bot:**
   ```python
   # In bot/telegram_handler.py, add this command:
   
   async def memories_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
       """Open the Memory Viewer mini app"""
       keyboard = [[
           InlineKeyboardButton(
               "🌟 View Memories",
               web_app=WebAppInfo(url=settings.MINIAPP_URL)
           )
       ]]
       reply_markup = InlineKeyboardMarkup(keyboard)
       
       await update.message.reply_text(
           "Click the button below to view your memories:",
           reply_markup=reply_markup
       )
   ```

3. **Register the command:**
   ```python
   # In setup_handlers():
   self.application.add_handler(CommandHandler("memories", self.memories_command))
   ```

## 🔒 Security

### Authentication Flow

1. User opens mini app from Telegram
2. Telegram provides `initData` with signature
3. Frontend sends `initData` in Authorization header
4. Backend verifies signature using bot token
5. Backend extracts user ID and processes request

### Signature Verification

The API uses HMAC-SHA256 to verify Telegram's signature:

```python
# Create secret key
secret_key = hmac.new(
    key=b"WebAppData",
    msg=bot_token.encode(),
    digestmod=hashlib.sha256
).digest()

# Verify signature
calculated_hash = hmac.new(
    key=secret_key,
    msg=data_check_string.encode(),
    digestmod=hashlib.sha256
).hexdigest()
```

### CORS Configuration

The API only accepts requests from Telegram domains:
- `https://web.telegram.org`
- `https://telegram.org`

## 🎨 Customization

### Theming

The mini app automatically adapts to the user's Telegram theme using CSS variables:

```css
:root {
    --tg-theme-bg-color: #ffffff;
    --tg-theme-text-color: #000000;
    --tg-theme-hint-color: #999999;
    --tg-theme-link-color: #2481cc;
    --tg-theme-button-color: #2481cc;
    --tg-theme-button-text-color: #ffffff;
    --tg-theme-secondary-bg-color: #f4f4f5;
}
```

### Adding New Views

1. Add a new tab in `index.html`:
   ```html
   <button class="tab" data-tab="myview">My View</button>
   ```

2. Add content container:
   ```html
   <div id="myview-content" class="content">
       <!-- Your content here -->
   </div>
   ```

3. Add API endpoint in `miniapp/api.py`:
   ```python
   @app.get("/api/myview")
   async def get_myview(authorization: str = Header(...)):
       # Your logic here
       pass
   ```

4. Add loader function in JavaScript:
   ```javascript
   async function loadMyView() {
       const data = await apiCall('/api/myview');
       // Render data
   }
   ```

## 📊 Performance

- **Lazy Loading**: Data is only loaded when tabs are clicked
- **Pagination**: Conversations support offset-based pagination
- **Caching**: Browser caches static assets
- **Efficient Queries**: Database queries use proper indexing

## 🐛 Troubleshooting

### "Invalid signature" error
- Ensure `TELEGRAM_BOT_TOKEN` is correct in `.env`
- Check that the mini app URL matches the one registered in BotFather
- Verify CORS settings allow Telegram domains

### "User not found" error
- User must have interacted with the bot at least once
- Check database connection
- Verify user exists in the database

### Mini app doesn't load
- Check that API server is running
- Verify `MINIAPP_URL` is accessible
- Check browser console for errors
- Ensure HTTPS is used in production

### Styling issues
- Clear browser cache
- Check that Telegram theme variables are being applied
- Test in Telegram's built-in browser

## 📝 License

Copyright 2026 Simon Ryu

Licensed under the Apache License, Version 2.0. See [LICENSE](../LICENSE) for details.

## 🙏 Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Telegram WebApp](https://core.telegram.org/bots/webapps) - Telegram Mini Apps platform
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM