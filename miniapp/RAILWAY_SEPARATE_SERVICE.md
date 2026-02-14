# 🚂 Railway Deployment - Separate Mini App Service

**Recommended Setup**: Deploy the Mini App API as a separate Railway service from your main bot.

## 🎯 Why Separate Services?

### Benefits
- ✅ **Independent Scaling** - Scale bot and API separately based on usage
- ✅ **Better Resource Management** - Each service gets its own resources
- ✅ **Easier Debugging** - Separate logs for bot and API
- ✅ **Zero Downtime Updates** - Update one without affecting the other
- ✅ **Cost Optimization** - Only pay for what each service uses

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Railway Project                       │
│                                                          │
│  ┌──────────────────────┐    ┌─────────────────────┐   │
│  │   Service 1: Bot     │    │ Service 2: Mini App │   │
│  │                      │    │                     │   │
│  │  ┌────────────────┐ │    │ ┌─────────────────┐ │   │
│  │  │ Telegram Bot   │ │    │ │  FastAPI Server │ │   │
│  │  │   (main.py)    │ │    │ │ (miniapp/api.py)│ │   │
│  │  │                │ │    │ │                 │ │   │
│  │  │ Webhook Mode   │ │    │ │  Port: 8000     │ │   │
│  │  └────────┬───────┘ │    │ └────────┬────────┘ │   │
│  │           │          │    │          │          │   │
│  │  Bot URL: │          │    │  API URL:│          │   │
│  │  aki-bot. │          │    │  aki-api.│          │   │
│  │  railway  │          │    │  railway │          │   │
│  └───────────┼──────────┘    └──────────┼──────────┘   │
│              │                           │              │
│              └───────────┬───────────────┘              │
│                          │                              │
│              ┌───────────▼──────────┐                   │
│              │  PostgreSQL Database │                   │
│              │   (Shared Resource)  │                   │
│              └──────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Step-by-Step Setup

### Step 1: Deploy the Bot Service (If Not Already Done)

```bash
# Navigate to your project
cd /path/to/aki-the-bot

# Login to Railway
railway login

# Create new project (or link existing)
railway init

# Name it something like "aki-bot"
```

**Set Bot Environment Variables:**

```bash
railway variables set TELEGRAM_BOT_TOKEN="your_bot_token"
railway variables set OPENAI_API_KEY="your_openai_key"
railway variables set ENVIRONMENT="production"
railway variables set LOG_LEVEL="INFO"

# Add PostgreSQL if not already added
railway add --database postgresql

# Note: Railway will auto-set DATABASE_URL
```

**Deploy Bot:**

```bash
# Make sure Procfile contains:
# web: python main.py

railway up
railway domain  # Get bot URL, e.g., aki-bot-production.up.railway.app
```

### Step 2: Create Mini App Service

**Option A: Same Repository (Recommended)**

```bash
# In the same project directory
# Create a new service in the same Railway project

# Via Railway Dashboard:
# 1. Go to your Railway project
# 2. Click "New Service"
# 3. Select "GitHub Repo" (same repo)
# 4. Name it "aki-miniapp"
```

**Option B: Via CLI**

```bash
# Create new service in same project
railway service create aki-miniapp

# Link to the service
railway service link aki-miniapp
```

### Step 3: Configure Mini App Service

**Create `Procfile.miniapp`** (or configure in Railway dashboard):

```
web: python miniapp/run_api.py
```

**Set Mini App Environment Variables:**

```bash
# Switch to mini app service
railway service link aki-miniapp

# Set variables
railway variables set TELEGRAM_BOT_TOKEN="your_bot_token"  # Needed for auth
railway variables set MINIAPP_PORT="8000"
railway variables set ENVIRONMENT="production"
railway variables set LOG_LEVEL="INFO"

# Link to the same database
# In Railway dashboard: Settings → Variables → Reference → Select PostgreSQL
# Or set manually:
railway variables set DATABASE_URL="postgresql://..."
```

### Step 4: Deploy Mini App

```bash
# Deploy mini app service
railway up

# Get mini app URL
railway domain
# Example: aki-miniapp-production.up.railway.app
```

### Step 5: Link Services Together

**Update Bot Service with Mini App URL:**

```bash
# Switch back to bot service
railway service link aki-bot

# Set mini app URL
railway variables set MINIAPP_URL="https://aki-miniapp-production.up.railway.app"

# Redeploy bot
railway up
```

### Step 6: Configure in BotFather

1. Open [@BotFather](https://t.me/botfather)
2. Send `/newapp`
3. Select your bot
4. Enter details:
   - **Title**: Memory Viewer
   - **Description**: View your conversation memories with Aki
   - **Short name**: memories
   - **Web App URL**: `https://aki-miniapp-production.up.railway.app`

### Step 7: Test Everything

```bash
# Test bot service
curl https://aki-bot-production.up.railway.app/

# Test mini app service
curl https://aki-miniapp-production.up.railway.app/
# Should return: {"status":"ok","service":"Aki Memory Viewer API"}

# Test in Telegram
# 1. Send /memories to your bot
# 2. Click the button
# 3. Mini app should open
```

## 📋 Configuration Summary

### Service 1: Bot

**Procfile:**
```
web: python main.py
```

**Environment Variables:**
```
TELEGRAM_BOT_TOKEN=your_token
OPENAI_API_KEY=your_key
DATABASE_URL=postgresql://...  (auto-set by Railway)
MINIAPP_URL=https://aki-miniapp-production.up.railway.app
WEBHOOK_URL=https://aki-bot-production.up.railway.app
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Service 2: Mini App

**Procfile:**
```
web: python miniapp/run_api.py
```

**Environment Variables:**
```
TELEGRAM_BOT_TOKEN=your_token  (for signature verification)
DATABASE_URL=postgresql://...  (same as bot)
MINIAPP_PORT=8000
MINIAPP_URL=https://aki-miniapp-production.up.railway.app
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 🔧 Railway Dashboard Configuration

### For Mini App Service

1. **Go to Railway Dashboard** → Your Project → Mini App Service
2. **Settings** → **Build**:
   - Build Command: `uv sync`
   - Start Command: `python miniapp/run_api.py`
3. **Settings** → **Deploy**:
   - Root Directory: `/` (leave as root)
   - Watch Paths: `miniapp/**` (optional, to only redeploy on miniapp changes)

### Sharing Database Between Services

**Method 1: Reference Variable (Recommended)**

1. Go to Mini App Service → Variables
2. Click "New Variable"
3. Select "Reference" tab
4. Choose PostgreSQL → DATABASE_URL
5. This automatically keeps them in sync

**Method 2: Manual Copy**

1. Copy DATABASE_URL from bot service
2. Paste into mini app service variables
3. Must update manually if database changes

## 📊 Monitoring Both Services

### View Logs

```bash
# Bot logs
railway service link aki-bot
railway logs

# Mini app logs
railway service link aki-miniapp
railway logs

# Or view in dashboard
# Project → Service → Logs tab
```

### Check Status

```bash
# Bot status
railway service link aki-bot
railway status

# Mini app status
railway service link aki-miniapp
railway status
```

### Resource Usage

In Railway Dashboard:
- Project → Service → Metrics
- View CPU, Memory, Network usage
- Set up alerts for high usage

## 💰 Cost Breakdown

### Free Tier (per service)

Each service gets:
- $5 credit/month (shared across project)
- 500 hours execution time
- 1GB RAM
- 100GB bandwidth

### Estimated Usage

**Bot Service:**
- ~200-300 hours/month (always running)
- ~200-500MB RAM
- ~$2-3/month

**Mini App Service:**
- ~100-200 hours/month (on-demand)
- ~200-400MB RAM
- ~$1-2/month

**Total: ~$3-5/month** (within free tier for small usage)

## 🔄 Deployment Workflow

### Update Bot Only

```bash
# Make changes to bot code
git add bot/ agents/ prompts/
git commit -m "Update bot logic"
git push

# Railway auto-deploys bot service
# Mini app service unaffected
```

### Update Mini App Only

```bash
# Make changes to mini app
git add miniapp/
git commit -m "Update mini app UI"
git push

# Railway auto-deploys mini app service
# Bot service unaffected
```

### Update Both

```bash
# Make changes to both
git add .
git commit -m "Update bot and mini app"
git push

# Railway deploys both services
```

## 🐛 Troubleshooting

### Issue: Services can't connect to database

**Solution:**
```bash
# Verify both services have DATABASE_URL
railway service link aki-bot
railway variables get DATABASE_URL

railway service link aki-miniapp
railway variables get DATABASE_URL

# They should be identical
```

### Issue: Bot can't reach mini app

**Solution:**
```bash
# Verify MINIAPP_URL in bot service
railway service link aki-bot
railway variables get MINIAPP_URL

# Should match mini app's public URL
railway service link aki-miniapp
railway domain
```

### Issue: "Invalid signature" in mini app

**Solution:**
```bash
# Ensure both services have same TELEGRAM_BOT_TOKEN
railway service link aki-bot
railway variables get TELEGRAM_BOT_TOKEN

railway service link aki-miniapp
railway variables get TELEGRAM_BOT_TOKEN

# They must match exactly
```

### Issue: High costs

**Solution:**
1. Check which service is using more resources
2. Consider scaling down or optimizing
3. Use Railway's sleep mode for low-traffic periods
4. Monitor in Dashboard → Metrics

## 🎯 Best Practices

### 1. Use Environment-Specific Configs

```bash
# Development
railway variables set ENVIRONMENT="development"
railway variables set LOG_LEVEL="DEBUG"

# Production
railway variables set ENVIRONMENT="production"
railway variables set LOG_LEVEL="INFO"
```

### 2. Set Up Health Checks

Both services should respond to health checks:

**Bot:** `GET /` or `GET /health`
**Mini App:** `GET /` returns `{"status":"ok"}`

### 3. Enable Auto-Deploy

In Railway Dashboard:
- Settings → GitHub → Enable Auto-Deploy
- Deploys automatically on git push

### 4. Use Staging Environment

Create separate Railway projects:
- `aki-production` - Production services
- `aki-staging` - Testing services

### 5. Monitor Logs Regularly

```bash
# Set up log alerts in Railway dashboard
# Settings → Notifications → Add webhook
```

## 📈 Scaling

### When to Scale

Scale when you see:
- High CPU usage (>80%)
- High memory usage (>80%)
- Slow response times
- Frequent restarts

### How to Scale

**Vertical Scaling (More Resources):**
- Railway Dashboard → Service → Settings → Resources
- Increase RAM/CPU allocation

**Horizontal Scaling (More Instances):**
- Railway Pro plan required
- Settings → Replicas → Increase count

## ✅ Verification Checklist

- [ ] Bot service deployed and running
- [ ] Mini app service deployed and running
- [ ] Both services connected to same database
- [ ] Bot has MINIAPP_URL set correctly
- [ ] Mini app has TELEGRAM_BOT_TOKEN set
- [ ] Public domains generated for both
- [ ] Web App configured in BotFather
- [ ] `/memories` command works
- [ ] Mini app opens in Telegram
- [ ] All tabs load data correctly
- [ ] Logs show no errors

## 🎉 Success!

You now have:
- ✅ Bot running as separate service
- ✅ Mini App API as separate service
- ✅ Shared PostgreSQL database
- ✅ Independent scaling and monitoring
- ✅ Better resource management

Users can now view their memories by sending `/memories` to your bot!

---

**Need help?** Check the [Railway Documentation](https://docs.railway.app) or open an issue on GitHub.