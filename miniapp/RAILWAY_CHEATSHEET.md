# 🚂 Railway Separate Services - Quick Reference

One-page cheatsheet for deploying bot and mini app as separate Railway services.

## 📋 Quick Setup Commands

### Service 1: Bot

```bash
# Create/link bot service
railway service create aki-bot
railway service link aki-bot

# Set variables
railway variables set TELEGRAM_BOT_TOKEN="your_token"
railway variables set OPENAI_API_KEY="your_key"
railway variables set ENVIRONMENT="production"

# Add database
railway add --database postgresql

# Deploy
railway up
railway domain  # Save this URL
```

### Service 2: Mini App

```bash
# Create mini app service (in same project)
railway service create aki-miniapp
railway service link aki-miniapp

# Set variables
railway variables set TELEGRAM_BOT_TOKEN="your_token"
railway variables set MINIAPP_PORT="8000"
railway variables set ENVIRONMENT="production"

# Link to same database (in dashboard: Variables → Reference → PostgreSQL)

# Deploy
railway up
railway domain  # Save this URL
```

### Link Services

```bash
# Update bot with mini app URL
railway service link aki-bot
railway variables set MINIAPP_URL="https://aki-miniapp-xxx.up.railway.app"
railway up
```

## 🔧 Configuration

### Bot Service (`aki-bot`)

**Procfile:**
```
web: python main.py
```

**Required Variables:**
```
TELEGRAM_BOT_TOKEN=xxx
OPENAI_API_KEY=xxx
DATABASE_URL=postgresql://...  (auto-set)
MINIAPP_URL=https://aki-miniapp-xxx.up.railway.app
ENVIRONMENT=production
```

### Mini App Service (`aki-miniapp`)

**Procfile:**
```
web: python miniapp/run_api.py
```

**Required Variables:**
```
TELEGRAM_BOT_TOKEN=xxx  (same as bot)
DATABASE_URL=postgresql://...  (reference from PostgreSQL)
MINIAPP_PORT=8000
MINIAPP_URL=https://aki-miniapp-xxx.up.railway.app
ENVIRONMENT=production
```

## 🎯 BotFather Setup

```
/newapp
→ Select your bot
→ Title: Memory Viewer
→ Description: View your conversation memories
→ Short name: memories
→ Web App URL: https://aki-miniapp-xxx.up.railway.app
```

## 🔍 Testing

```bash
# Test bot
curl https://aki-bot-xxx.up.railway.app/

# Test mini app
curl https://aki-miniapp-xxx.up.railway.app/
# Should return: {"status":"ok","service":"Aki Memory Viewer API"}

# Test in Telegram
/memories → Click button → Mini app opens
```

## 📊 Monitoring

```bash
# View bot logs
railway service link aki-bot
railway logs

# View mini app logs
railway service link aki-miniapp
railway logs

# Check status
railway status
```

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| "Module not found" | `railway run uv sync && railway up` |
| "Invalid signature" | Verify TELEGRAM_BOT_TOKEN matches in both services |
| "Database connection failed" | Check DATABASE_URL is set in both services |
| "Can't reach mini app" | Verify MINIAPP_URL in bot service matches mini app domain |

## 💰 Cost Estimate

- Bot Service: ~$2-3/month
- Mini App Service: ~$1-2/month
- **Total: ~$3-5/month** (within free tier)

## 🔄 Update Workflow

```bash
# Update bot only
git add bot/ agents/ prompts/
git commit -m "Update bot"
git push  # Auto-deploys bot service

# Update mini app only
git add miniapp/
git commit -m "Update mini app"
git push  # Auto-deploys mini app service
```

## ✅ Checklist

- [ ] Bot service created and deployed
- [ ] Mini app service created and deployed
- [ ] Both services share same DATABASE_URL
- [ ] Bot has MINIAPP_URL set
- [ ] Mini app has TELEGRAM_BOT_TOKEN set
- [ ] Domains generated for both
- [ ] Web App configured in BotFather
- [ ] `/memories` command works
- [ ] Mini app loads in Telegram

## 📞 Quick Links

- **Railway Dashboard**: https://railway.app/dashboard
- **Bot Logs**: Dashboard → aki-bot → Logs
- **Mini App Logs**: Dashboard → aki-miniapp → Logs
- **BotFather**: https://t.me/botfather

---

**That's it!** Two separate services, better scaling, easier management. 🎉