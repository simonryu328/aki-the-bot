# Railway Deployment Guide

## Prerequisites
- GitHub account with this repository pushed
- Railway account (sign up at https://railway.app)
- All API keys ready (Telegram, OpenAI, Anthropic)

## Files Created for Deployment
- ✅ `Procfile` - Tells Railway how to run the bot
- ✅ `railway.json` - Railway configuration
- ✅ `requirements.txt` - Python dependencies
- ✅ `runtime.txt` - Python version specification
- ✅ `.railwayignore` - Files to exclude from deployment

## Deployment Steps

### 1. Push to GitHub
```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### 2. Create Railway Project
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `aki-the-bot` repository
5. Railway will auto-detect Python and start building

### 3. Add PostgreSQL Database
1. In your Railway project, click "+ New"
2. Select "Database" → "PostgreSQL"
3. Railway automatically creates `DATABASE_URL` environment variable
4. The bot will connect to this database automatically

### 4. Set Environment Variables
In Railway project settings → Variables, add:

**Required:**
- `TELEGRAM_BOT_TOKEN` - Your bot token from @BotFather
- `OPENAI_API_KEY` - Your OpenAI API key
- `ANTHROPIC_API_KEY` - Your Anthropic API key (if using Claude)
- `ENVIRONMENT` - Set to `production`

**Optional:**
- `PINECONE_API_KEY` - If using vector store
- `LOG_LEVEL` - Set to `INFO` or `DEBUG`
- `TIMEZONE` - Default is `America/Toronto`

**Note:** `DATABASE_URL` is automatically set by Railway when you add PostgreSQL

### 5. Initialize Database Tables
After first deployment, run this command in Railway's terminal:
```bash
python scripts/init_db_async.py
```

Or use Railway's "Run a Command" feature in the deployment settings.

### 6. Migrate Local Data (Optional)
If you have existing data to migrate:

1. **Export local database:**
```bash
pg_dump -U your_username -d ai_companion -F c -f backup.dump
```

2. **Get Railway database URL:**
   - Railway dashboard → PostgreSQL service → "Connect"
   - Copy the connection string

3. **Import to Railway:**
```bash
pg_restore -d "railway_connection_string" backup.dump
```

### 7. Deploy and Monitor
1. Railway auto-deploys on every git push
2. Monitor logs in Railway dashboard
3. Check deployment status
4. Test bot by sending a message on Telegram

## Verification Checklist
- [ ] Bot responds to messages on Telegram
- [ ] Database tables created (users, conversations, diary_entries, scheduled_messages)
- [ ] Reach-out system working (check logs after 6+ hours of inactivity)
- [ ] No errors in Railway logs
- [ ] Environment variables all set correctly

## Troubleshooting

### "Module not found" errors
- Check `requirements.txt` includes all dependencies
- Redeploy: `git commit --allow-empty -m "Trigger redeploy" && git push`

### Database connection errors
- Verify `DATABASE_URL` is set in Railway
- Check PostgreSQL service is running
- Run `init_db_async.py` to create tables

### Bot not responding
- Check Railway logs for errors
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure deployment is "Active" in Railway

### Out of memory
- Upgrade Railway plan (free tier has 512MB RAM limit)
- Check for memory leaks in logs

## Cost Estimate
**Railway Pricing:**
- Free: $5 credit/month (enough for small bot)
- Hobby: $5/month for 500 hours
- Pro: $20/month for unlimited

**Typical Usage:**
- Bot: ~$2-3/month
- PostgreSQL: ~$1-2/month
- **Total: ~$3-5/month** (covered by free tier initially)

## Updating the Bot
```bash
# Make changes locally
git add .
git commit -m "Update bot features"
git push origin main

# Railway auto-deploys on push
```

## Rollback
If deployment fails:
1. Railway dashboard → Deployments
2. Click on previous successful deployment
3. Click "Redeploy"

## Support
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Check Railway logs for detailed error messages