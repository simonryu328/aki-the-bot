# Telegram Mini App Setup Guide

Complete step-by-step guide to set up and deploy the Memory Viewer mini app.

## 📋 Prerequisites

- Telegram Bot created via [@BotFather](https://t.me/botfather)
- PostgreSQL database (local or hosted)
- Python 3.11+
- Domain with HTTPS (for production)

## 🚀 Quick Start (Local Development)

### 1. Install Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 2. Configure Environment

Create or update `.env` file:

```env
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/aki_companion

# Mini App Configuration
MINIAPP_PORT=8000
MINIAPP_URL=http://localhost:8000

# Optional
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### 3. Initialize Database

```bash
# Create database tables
uv run python scripts/init_db.py
```

### 4. Start the API Server

```bash
# Terminal 1: Start the mini app API
uv run python miniapp/run_api.py
```

The API will be available at `http://localhost:8000`

### 5. Test Locally

Open `http://localhost:8000/miniapp/index.html` in your browser to test the interface.

**Note:** For full Telegram integration testing, you'll need to expose your local server using ngrok or similar.

## 🌐 Production Deployment

### Option 1: Railway (Recommended)

Railway provides easy deployment with automatic HTTPS.

#### Step 1: Prepare Your Project

1. Ensure your code is in a Git repository
2. Create `Procfile` in project root:

```
web: python miniapp/run_api.py
```

3. Update `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python miniapp/run_api.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

#### Step 2: Deploy to Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Link to your project
railway link

# Set environment variables
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set OPENAI_API_KEY=your_key
railway variables set DATABASE_URL=your_database_url
railway variables set MINIAPP_PORT=8000
railway variables set ENVIRONMENT=production

# Deploy
railway up
```

#### Step 3: Get Your URL

```bash
# Get the public URL
railway domain
```

Your mini app will be available at: `https://your-app.up.railway.app`

#### Step 4: Update Environment Variable

```bash
# Set the mini app URL
railway variables set MINIAPP_URL=https://your-app.up.railway.app
```

### Option 2: Docker Deployment

#### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "miniapp/run_api.py"]
```

#### Build and Run

```bash
# Build image
docker build -t aki-miniapp .

# Run container
docker run -d \
  -p 8000:8000 \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e OPENAI_API_KEY=your_key \
  -e DATABASE_URL=your_database_url \
  -e MINIAPP_URL=https://your-domain.com \
  --name aki-miniapp \
  aki-miniapp
```

### Option 3: Traditional VPS

#### Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Setup Application

```bash
# Clone repository
git clone your-repo-url
cd aki-the-bot

# Install dependencies
uv sync

# Create systemd service
sudo nano /etc/systemd/system/aki-miniapp.service
```

Add this content:

```ini
[Unit]
Description=Aki Mini App API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/aki-the-bot
Environment="PATH=/home/your-user/.local/bin:/usr/bin"
ExecStart=/home/your-user/.local/bin/uv run python miniapp/run_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable aki-miniapp
sudo systemctl start aki-miniapp

# Check status
sudo systemctl status aki-miniapp
```

#### Setup Nginx Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/aki-miniapp
```

Add:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site and get SSL:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/aki-miniapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate with Certbot
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

## 🤖 Telegram Bot Configuration

### Step 1: Create Web App in BotFather

1. Open [@BotFather](https://t.me/botfather) in Telegram
2. Send `/newapp`
3. Select your bot
4. Enter app details:
   - **Title:** Memory Viewer
   - **Description:** View your conversation memories with Aki
   - **Photo:** Upload a 640x360 PNG image
   - **Demo GIF/Video:** (Optional) Upload a demo
   - **Short name:** memories (must be unique)
   - **Web App URL:** Your deployed URL (e.g., `https://your-app.up.railway.app`)

### Step 2: Set Bot Commands

Send to BotFather:

```
/setcommands

start - Start chatting with Aki
memories - View your conversation memories
debug - Show debug information
reset - Reset conversation history
reachout_settings - View reach-out settings
```

### Step 3: Test the Integration

1. Open your bot in Telegram
2. Send `/memories`
3. Click the "🌟 View Your Memories" button
4. The mini app should open with your data

## 🔧 Configuration Options

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Bot token from BotFather |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `DATABASE_URL` | Yes | - | PostgreSQL connection URL |
| `MINIAPP_PORT` | No | 8000 | Port for API server |
| `MINIAPP_URL` | Yes | - | Public URL for mini app |
| `LOG_LEVEL` | No | INFO | Logging level |
| `ENVIRONMENT` | No | development | Environment (development/production) |

### Database Configuration

The mini app uses the same database as the main bot. Ensure your `DATABASE_URL` is properly configured:

```
postgresql://username:password@host:port/database
```

For Railway PostgreSQL:
```
postgresql://postgres:password@containers-us-west-123.railway.app:5432/railway
```

## 🧪 Testing

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/

# Test with mock auth (development only)
curl -H "Authorization: Bearer test" http://localhost:8000/api/user/stats
```

### Test in Telegram

1. Use Telegram's test environment (optional)
2. Send `/memories` command
3. Verify mini app opens correctly
4. Check all tabs load data
5. Test on different devices (iOS, Android, Desktop)

## 🐛 Troubleshooting

### API Server Won't Start

**Error:** `Port already in use`
```bash
# Find process using port 8000
lsof -i :8000
# Kill the process
kill -9 <PID>
```

**Error:** `Module not found`
```bash
# Reinstall dependencies
uv sync --reinstall
```

### Mini App Shows "Invalid Signature"

1. Verify `TELEGRAM_BOT_TOKEN` is correct
2. Check that `MINIAPP_URL` matches the URL in BotFather
3. Ensure you're using HTTPS in production
4. Clear browser cache and try again

### Data Not Loading

1. Check API server logs: `railway logs` or `journalctl -u aki-miniapp -f`
2. Verify database connection
3. Ensure user has interacted with bot at least once
4. Check browser console for errors

### CORS Errors

The API only accepts requests from Telegram domains. If testing locally:

1. Use ngrok or similar to get HTTPS URL
2. Update `MINIAPP_URL` to ngrok URL
3. Update Web App URL in BotFather

## 📊 Monitoring

### Check API Health

```bash
# Railway
railway logs

# Docker
docker logs aki-miniapp

# Systemd
journalctl -u aki-miniapp -f
```

### Monitor Database

```bash
# Check database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size(current_database()));"

# Check table sizes
psql $DATABASE_URL -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## 🔒 Security Best Practices

1. **Always use HTTPS in production**
2. **Keep bot token secret** - never commit to Git
3. **Use environment variables** for all sensitive data
4. **Enable rate limiting** if needed
5. **Monitor API usage** for unusual patterns
6. **Keep dependencies updated**: `uv sync --upgrade`
7. **Use strong database passwords**
8. **Restrict database access** to API server only

## 📈 Performance Optimization

### Database Indexing

Ensure these indexes exist (should be created by migrations):

```sql
CREATE INDEX idx_conversations_user_timestamp ON conversations(user_id, timestamp);
CREATE INDEX idx_diary_entries_user_type ON diary_entries(user_id, entry_type);
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
```

### Caching

Consider adding Redis for caching frequently accessed data:

```python
# Example: Cache user stats for 5 minutes
from redis import Redis
redis = Redis(host='localhost', port=6379)

@app.get("/api/user/stats")
async def get_user_stats(...):
    cache_key = f"stats:{telegram_id}"
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # ... fetch from database ...
    
    redis.setex(cache_key, 300, json.dumps(stats))
    return stats
```

## 🎉 Success!

Your Telegram Mini App is now live! Users can:

- View their conversation memories
- Browse full chat history
- Access diary entries
- See activity timeline

For support, check the main [README](README.md) or open an issue on GitHub.