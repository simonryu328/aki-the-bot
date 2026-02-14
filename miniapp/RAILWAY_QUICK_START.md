# 🚂 Railway Quick Start - 5 Minutes Setup

The fastest way to get your Telegram Mini App running on Railway.

## 🎯 What You'll Get

After following this guide, you'll have:
- ✅ Telegram bot running 24/7
- ✅ Mini App API serving memory viewer
- ✅ PostgreSQL database (free tier)
- ✅ HTTPS domain automatically
- ✅ `/memories` command working in Telegram

## ⚡ Quick Setup (5 minutes)

### 1. One-Click Deploy

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login to Railway
railway login

# Initialize in your project directory
cd /path/to/aki-the-bot
railway init

# Add PostgreSQL database
railway add --database postgresql
```

### 2. Set Environment Variables

```bash
# Required variables
railway variables set TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
railway variables set OPENAI_API_KEY="your_openai_api_key"
railway variables set MINIAPP_PORT="8000"
railway variables set ENVIRONMENT="production"

# Railway will auto-set DATABASE_URL from PostgreSQL addon
```

### 3. Deploy

```bash
# Deploy your code
railway up

# Get your public URL
railway domain
# Example output: aki-bot-production.up.railway.app
```

### 4. Configure Mini App URL

```bash
# Set the mini app URL (use the domain from step 3)
railway variables set MINIAPP_URL="https://aki-bot-production.up.railway.app"

# Redeploy to apply
railway up
```

### 5. Configure in Telegram

1. Open [@BotFather](https://t.me/botfather)
2. Send `/newapp`
3. Select your bot
4. Enter:
   - **Title**: Memory Viewer
   - **Description**: View your conversation memories
   - **Short name**: memories
   - **Web App URL**: `https://aki-bot-production.up.railway.app`

### 6. Test It!

1. Open your bot in Telegram
2. Send `/memories`
3. Click the button
4. 🎉 Your mini app opens!

## 📊 Architecture on Railway

```
┌─────────────────────────────────────────────────┐
│           Railway Service (Single)               │
│                                                  │
│  ┌──────────────┐         ┌─────────────────┐  │
│  │ Telegram Bot │         │  Mini App API   │  │
│  │  (main.py)   │         │ (miniapp/api.py)│  │
│  │              │         │                 │  │
│  │ Port: N/A    │         │ Port: 8000      │  │
│  │ (Webhook)    │         │ (HTTP Server)   │  │
│  └──────┬───────┘         └────────┬────────┘  │
│         │                          │            │
│         └──────────┬───────────────┘            │
│                    │                            │
│         ┌──────────▼──────────┐                 │
│         │  PostgreSQL DB      │                 │
│         │  (Railway Addon)    │                 │
│         └─────────────────────┘                 │
│                                                  │
│  Public URL: https://your-app.up.railway.app    │
└─────────────────────────────────────────────────┘
```

## 🔧 How It Works

### Single Process Deployment

Railway runs `start_all.py` which:
1. Starts the Telegram bot in one process
2. Starts the Mini App API in another process
3. Both share the same database
4. Both run on the same Railway service

### URL Structure

- **Bot Webhook**: `https://your-app.up.railway.app/webhook`
- **Mini App**: `https://your-app.up.railway.app/` (root)
- **API Endpoints**: `https://your-app.up.railway.app/api/*`
- **Health Check**: `https://your-app.up.railway.app/`

### Environment Variables

Railway automatically provides:
- `DATABASE_URL` - PostgreSQL connection string
- `PORT` - Port to bind to (Railway manages this)

You need to set:
- `TELEGRAM_BOT_TOKEN` - From BotFather
- `OPENAI_API_KEY` - Your OpenAI key
- `MINIAPP_URL` - Your Railway domain
- `MINIAPP_PORT` - 8000 (or use Railway's PORT)

## 📝 Files Used

```
aki-the-bot/
├── start_all.py          # Starts both bot and API
├── main.py               # Telegram bot entry point
├── Procfile              # Railway startup command
├── pyproject.toml        # Dependencies
├── miniapp/
│   ├── api.py           # FastAPI backend
│   ├── index.html       # Frontend interface
│   └── run_api.py       # API startup script
└── config/
    └── settings.py      # Configuration
```

## 🎛️ Procfile Configuration

Your `Procfile` should contain:

```
web: python start_all.py
```

This tells Railway to run both services together.

## 🔍 Verify Deployment

### Check Logs

```bash
# View real-time logs
railway logs

# You should see:
# 🤖 Starting Telegram bot...
# 🌐 Starting Mini App API...
# ✅ Both services started successfully
```

### Test API

```bash
# Health check
curl https://your-app.up.railway.app/

# Should return: {"status":"ok","service":"Aki Memory Viewer API"}
```

### Test in Telegram

1. Send `/start` to your bot
2. Send `/memories`
3. Click "🌟 View Your Memories"
4. Mini app should open

## 🐛 Common Issues

### Issue: "Module not found"

**Solution**: Dependencies not installed
```bash
railway run uv sync
railway up
```

### Issue: "Port already in use"

**Solution**: Railway manages ports automatically. Ensure your code uses:
```python
port = int(os.environ.get("PORT", 8000))
```

### Issue: "Invalid signature" in mini app

**Solution**: 
1. Check `TELEGRAM_BOT_TOKEN` is correct
2. Verify `MINIAPP_URL` matches your Railway domain
3. Ensure using HTTPS (Railway provides this)

### Issue: Database connection fails

**Solution**: 
```bash
# Check if PostgreSQL addon is added
railway add --database postgresql

# Verify DATABASE_URL is set
railway variables get DATABASE_URL
```

## 💰 Cost

Railway Free Tier includes:
- **$5 credit/month**
- **500 hours execution time**
- **1GB RAM per service**
- **100GB bandwidth**

This is enough for:
- ~100-500 users
- ~10,000 messages/day
- Small to medium usage

## 📈 Monitoring

### View Metrics

```bash
# Check service status
railway status

# View resource usage
railway metrics
```

### Railway Dashboard

Visit [railway.app/dashboard](https://railway.app/dashboard) to:
- View deployment history
- Monitor resource usage
- Check logs
- Manage environment variables

## 🚀 Next Steps

1. ✅ Deploy to Railway (done!)
2. ✅ Configure in BotFather (done!)
3. 📱 Test with real users
4. 📊 Monitor usage in Railway dashboard
5. 🎨 Customize the mini app interface
6. 🔧 Add more features

## 🆘 Need Help?

- **Railway Docs**: https://docs.railway.app
- **Telegram Bot API**: https://core.telegram.org/bots/webapps
- **Project Issues**: Open an issue on GitHub

---

**That's it!** Your Telegram Mini App is now live on Railway. Users can view their memories by sending `/memories` to your bot. 🎉