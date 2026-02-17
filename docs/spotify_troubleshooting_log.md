# Spotify Integration & Mini App Troubleshooting Log

This document captures the key technical hurdles and solutions encountered during the integration of Spotify into the Aki Telegram Mini App.

## 1. The "Double App" & Safari Handoff Issue
**Problem:** Redirecting from the Spotify OAuth callback directly to the Mini App URL caused the app to open inside a Safari tab rather than returning to the Telegram session. Using a deep link to the specific app (`t.me/AkiTheBot/aki`) caused a duplicate instance of the app to launch over the original one.

**Solution:**
- **Success Page:** The callback now returns a clean `HTMLResponse` ("Aki is Connected!") instead of a redirect.
- **Deep Link Handoff:** Added a "Back to Aki" button using `https://t.me/AkiTheBot`.
- **Logic:** This simply switches focus back to the Telegram chat. Since the original Mini App is already open as a "sheet" in that chat, the user returns to the existing session without duplicates.

## 2. Persistence & Caching "Ghosting"
**Problem:** After disconnecting or reconnecting, the UI would often show old data (e.g., still showing "Connect to Spotify" even after success, or showing a cached song after disconnect).

**Solutions:**
- **Frontend Cache-Busting:** Appended `?t=Date.now()` to the `/api/spotify/daily-soundtrack` fetch call.
- **Backend Headers:** Explicitly set `Cache-Control: no-cache, no-store, must-revalidate` using `JSONResponse`.
- **Server-Side Cache Eviction:** Forcefully deleted the user from the `memory_manager` cache (`_user_cache`) inside the callback and disconnect endpoints.
- **Visibility Refresh:** Added a `visibilitychange` listener in `main.ts` to trigger a fresh fetch whenever the user switches back to the Telegram app from Safari.

## 3. FastAPI Injection & Server Crashes
**Problem:** Attempting to inject the FastAPI `Response` object into a route that also returned a Pydantic-validated dict caused a `FastAPIError: Invalid args for response field`.

**Solution:**
- Switched from injecting `Response` to manually returning `JSONResponse(content=data, headers=headers)`. This bypassed the Pydantic validation conflict while still allowing custom header control.

## 4. Desktop Web Compatibility
**Problem:** Spotify's security headers prevent the login page from being embedded in an iframe (which is how Telegram Web Desktop loads Mini Apps), resulting in "Refused to connect."

**Solution:**
- Used `tg.openLink(url)` from the Telegram Web App SDK. This forces the login to open in a new tab/window, which is permitted by Spotify, rather than trying to load it within the Mini App's iframe.

## 5. Relative Redirection
**Problem:** Relying on a fixed `MINIAPP_URL` environment variable caused redirects to break if the domain changed or if Railway's internal networking differed from the public domain.

**Solution:**
- Switched to relative redirects for internal logic and handled external handoffs via the `t.me` deep link. This makes the app "location-blind" and more resilient to deployment changes.

## 6. Smart Polling for AI Generation
**Problem:** The LLM call for song recommendations takes 5–10 seconds. Users returning from the Spotify flow often landed back in the app before the generation was finished.

**Solution:**
- **Loading States:** Implemented a "Choosing your song..." state in the UI.
- **Auto-Retry:** The frontend now detects if a generation is in progress and automatically retries the fetch every 3 seconds until the data is ready.

---
**Current Bot Configuration (BotFather):**
- **Short Name:** `aki`
- **Bot Handle:** `@AkiTheBot`
- **Mini App URL:** `https://worker-production-08cb.up.railway.app`
