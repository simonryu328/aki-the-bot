# Railway Deployment Guide for Telegram Mini App

Complete guide for deploying the Aki Memory Viewer mini app on Railway.

## 🎯 Overview

Railway will host both:
1. **The Telegram bot** (main.py) - Handles chat interactions
2. **The Mini App API** (miniapp/api.py) - Serves the memory viewer web interface

You have two deployment options:
- **Option A**: Single Railway service (bot + mini app together)
- **Option B**: Two separate Railway services (recommended for scaling)

## 📋 Prerequisites

- Railway account (free tier works)
- GitHub repository with your code
- Telegram bot token from BotFather
- PostgreSQL database (Railway provides this)

## 🚀 Option A: Single Service Deployment (Simplest)

This runs both the bot and mini app API in one Railway service.

### Step 1: Prepare Your Code

The mini app API needs to run alongside the bot. We'll modify the startup to run both.

Create `start_all.py` in the project root:

```python
"""
Start both the Telegram bot and Mini App API server
"""
import multiprocessing
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_bot():
    """Run the Telegram bot"""
    logger.info("Starting Telegram bot...")
    from main import main
    main()

def run_miniapp():
    """Run the Mini App API"""
    logger.info("Starting Mini App API...")
    import uvicorn
    from miniapp.api import app
    from config.settings import settings
    
    port = settings.MINIAPP_PORT if hasattr(settings, 'MINIAPP_PORT') else 8000
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    # Start both processes
    bot_process = multiprocessing.Process(target=run_bot)
    api_process = multiprocessing.Process(target=run_miniapp)
    
    bot_process.start()
    api_process.start()
    
    try:
        bot_process.join()
        api_process.join()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bot_process.terminate()
        api_process.terminate()
        sys.exit(0)
```

### Step 2: Update Procfile

```
web: python start_all.py
```

### Step 3: Deploy to Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Create new project
railway init

# Link to your GitHub repo (or deploy directly)
railway link

# Add PostgreSQL database
railway add --database postgresql

# Set environment variables
railway variables set TELEGRAM_BOT_TOKEN=your_bot_token
railway variables set OPENAI_API_KEY=your_openai_key
railway variables set MINIAPP_PORT=8000
railway variables set ENVIRONMENT=production
railway variables set LOG_LEVEL=INFO

# Deploy
railway up
```

### Step 4: Get Your URL

```bash
# Generate a public domain
railway domain

# This will give you something like:
# https://aki-bot-production.up.railway.app
```

### Step 5: Configure Mini App URL

```bash
# Set the mini app URL to your Railway domain
railway variables set MINIAPP_URL=https://aki-bot-production.up.railway.app

# Redeploy to apply changes
railway up
```

### Step 6: Configure in BotFather

1. Open [@BotFather](https://t.me/botfather) in Telegram
2. Send `/newapp`
3. Select your bot
4. Fill in details:
   - **Title**: Memory Viewer
   - **Description**: View your conversation memories with Aki
   - **Photo**: Upload a 640x360 PNG
   - **Short name**: memories (must be unique)
   - **Web App URL**: `https://aki-bot-production.up.railway.app`

5. Set bot commands with `/setcommands`:
```
start - Start chatting with Aki
memories - View your conversation memories
debug - Show debug information
reset - Reset conversation history
```

### Step 7: Test

1. Open your bot in Telegram
2. Send `/memories`
3. Click "🌟 View Your Memories" button
4. Mini app should open with your data!

## 🔧 Option B: Two Separate Services (Recommended)

This approach gives you better control and scaling options.

### Service 1: Telegram Bot

**Repository**: Your main bot code
**Procfile**:
```
web: python main.py
```

**Environment Variables**:
```
TELEGRAM_BOT_TOKEN=your_token
OPENAI_API_KEY=your_key
DATABASE_URL=postgresql://... (from Railway PostgreSQL)
MINIAPP_URL=https://aki-miniapp.up.railway.app
WEBHOOK_URL=https://aki-bot.up.railway.app
```

### Service 2: Mini App API

**Repository**: Same repo or separate
**Procfile**:
```
web: python miniapp/run_api.py
```

**Environment Variables**:
```
TELEGRAM_BOT_TOKEN=your_token (needed for auth verification)
DATABASE_URL=postgresql://... (same database as bot)
MINIAPP_PORT=8000
MINIAPP_URL=https://aki-miniapp.up.railway.app
ENVIRONMENT=production
```

**Deploy Steps**:

```bash
# Create first service (bot)
railway init
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set OPENAI_API_KEY=your_key
railway up
railway domain  # Get bot URL

# Create second service (mini app)
railway init
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set DATABASE_URL=your_db_url
railway variables set MINIAPP_PORT=8000
railway up
railway domain  # Get mini app URL

# Update bot service with mini app URL
railway link [bot-service-id]
railway variables set MINIAPP_URL=https://aki-miniapp.up.railway.app
```

## 🗂️ Serving Static Files

Railway automatically serves files from your project. The mini app HTML will be accessible at:

```
https://your-app.up.railway.app/miniapp/index.html
```

Or you can configure FastAPI to serve it at the root:

```python
# In miniapp/api.py, add:
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve static files
app.mount("/static", StaticFiles(directory="miniapp"), name="static")

@app.get("/")
async def root():
    return FileResponse("miniapp/index.html")
```

## 🔍 Troubleshooting

### Issue: "Module not found" errors

**Solution**: Ensure all dependencies are in `pyproject.toml`:
```bash
railway run uv sync
railway up
```

### Issue: Mini app shows "Invalid signature"

**Solution**: 
1. Verify `TELEGRAM_BOT_TOKEN` is set correctly in Railway
2. Check that `MINIAPP_URL` matches the URL in BotFather
3. Ensure you're using HTTPS (Railway provides this automatically)

### Issue: Database connection fails

**Solution**:
```bash
# Check database URL
railway variables get DATABASE_URL

# Ensure it's in the correct format
postgresql://user:pass@host:port/database
```

### Issue: Port binding errors

**Solution**: Railway automatically sets the `PORT` environment variable. Update your code:

```python
# In miniapp/run_api.py
import os
port = int(os.environ.get("PORT", 8000))
```

### Issue: Can't access mini app URL

**Solution**:
1. Check Railway logs: `railway logs`
2. Verify service is running: `railway status`
3. Test API health: `curl https://your-app.up.railway.app/`

## 📊 Monitoring

### View Logs

```bash
# Real-time logs
railway logs

# Filter by service
railway logs --service bot
railway logs --service miniapp
```

### Check Resource Usage

```bash
# View metrics
railway status

# Check database size
railway run psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
```

### Set Up Alerts

1. Go to Railway dashboard
2. Select your project
3. Click "Settings" → "Notifications"
4. Add webhook or email alerts for:
   - Deployment failures
   - High memory usage
   - Database connection issues

## 💰 Cost Optimization

Railway free tier includes:
- $5 credit per month
- 500 hours of execution time
- 1GB RAM per service

**Tips to stay within free tier**:

1. **Use single service deployment** (Option A) to save resources
2. **Enable sleep mode** for low-traffic periods:
   ```bash
   railway variables set RAILWAY_SLEEP_ENABLED=true
   ```
3. **Monitor usage**: Check Railway dashboard regularly
4. **Optimize queries**: Add database indexes for faster queries
5. **Cache responses**: Use Redis for frequently accessed data

## 🔄 Updates and Redeployment

### Update Code

```bash
# Make changes locally
git add .
git commit -m "Update mini app"
git push

# Railway auto-deploys from GitHub
# Or manually deploy:
railway up
```

### Update Environment Variables

```bash
# Update a variable
railway variables set MINIAPP_URL=new_url

# View all variables
railway variables

# Delete a variable
railway variables delete OLD_VAR
```

### Rollback

```bash
# View deployments
railway deployments

# Rollback to previous deployment
railway rollback [deployment-id]
```

## 🎉 Success Checklist

- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Environment variables configured
- [ ] Code deployed successfully
- [ ] Public domain generated
- [ ] MINIAPP_URL set to Railway domain
- [ ] Web App configured in BotFather
- [ ] `/memories` command works in Telegram
- [ ] Mini app opens and loads data
- [ ] All tabs (Memories, Conversations, Diary, Timeline) work

## 📞 Support

If you encounter issues:

1. Check Railway logs: `railway logs`
2. Review [Railway documentation](https://docs.railway.app)
3. Check [Telegram Bot API docs](https://core.telegram.org/bots/webapps)
4. Open an issue on GitHub

## 🔗 Useful Links

- [Railway Dashboard](https://railway.app/dashboard)
- [Railway CLI Docs](https://docs.railway.app/develop/cli)
- [Telegram WebApp Docs](https://core.telegram.org/bots/webapps)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

---

**Note**: Railway's free tier is perfect for testing and small-scale deployments. For production use with many users, consider upgrading to a paid plan or using a dedicated VPS.