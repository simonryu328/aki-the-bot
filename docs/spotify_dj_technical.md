# Technical Documentation: Aki Spotify DJ Integration

This document outlines the AI Engineering architecture for Aki's "Daily Soundtrack" feature, covering data ingestion, prompt engineering, cost analysis, and scalability.

## 1. AI Data Strategy: The Context Triad
Aki uses a "Triad" of context to generate personalized music recommendations. This ensures the choice is technically accurate (user taste) but emotionally resonant (recent life events).

### A. Music Preference Context (Spotify API)
*   **Top Tracks:** Last 5 most-played tracks (sampled from multiple time ranges).
*   **Recent History:** Last 5 tracks actually played by the user.
*   **Raw Fields Ingested:** `track_name`, `artist_name`, `genres` (inferred).

### B. Life Milestone Context (Aki Memory)
*   **Conversational Memories:** The 3 most recent diary entries (summaries of multi-day themes).
*   **Smart Slicing (Deduplication):** Aki automatically detects the "timestamp cutoff" of the last summary. Any raw messages already captured in that summary are excluded from the `recent_history` block, leaving only the "delta" (what happened since the last reflection). 
*   **Immediate Context:** Last ~3-5 messages of raw text for "conversational glue."

### C. Behavioral Context (Time/Day)
*   The current day of the week and hour (e.g., Sunday morning vs. Tuesday late night).

---

## 2. The LLM Pipeline
### Model Selection
*   **Primary:** `Claude 3.5 Sonnet` (via `settings.MODEL_INSIGHTS`).
*   **Role:** Acts as a "Music Psychologist."

### Token Cost Analysis (Approximate)
| Component | Tokens (In) | Tokens (Out) |
| :--- | :--- | :--- |
| Systemic Prompt | 250 | - |
| Spotify Data (10 tracks) | 150 | - |
| Conversations (5 msgs) | 300 | - |
| AI Memories (3 entries) | 600 | - |
| **Total per Generation** | **~1,300** | **~150** |

**Cost per User:** At current pricing, one generation costs approximately **$0.005 (0.5 cents)**.

---

## 3. Trigger & Caching Logic
### "Daily Caching" Mechanism
The implementation uses a **Diary-based Cache** rather than a volatile memory cache (Redis).
1.  **Request:** User opens the "Today" tab.
2.  **DB Check:** Backend queries `diary_entries` for `entry_type = 'daily_soundtrack'` within the user's current calendar day.
3.  **Efficiency:**
    *   **Cache Hit:** Returns the stored JSON (0 LLM cost).
    *   **Cache Miss:** Triggers the SoulAgent generation, stores the result, and returns it.

### Scalability
*   **Database:** High. Using Indexed SQLAlchemy queries on `user_id` and `timestamp`.
*   **API Usage:** Low. Rate-limited at the application level to 1 generation per 24 hours.
*   **Fault Tolerance:** If Spotify API is down or tokens are expired, Aki falls back to "Connect Spotify" UI or generic inspirational quotes.

---

## 4. Spotify Data Structure (Reference)
The backend interacts with the Spotify Web API (via `spotipy`). 

### Example Internal Track Payload:
```json
{
  "name": "The Night We Met",
  "artist": "Lord Huron",
  "album_art": "https://i.scdn.co/image/ab67616d0000b273...",
  "spotify_url": "https://open.spotify.com/track/...",
  "uri": "spotify:track:09mEisA99966pAtvM9S9sy",
  "preview_url": "https://p.scdn.co/mp3-preview/..."
}
```

### LLM Output Schema:
The LLM is constrained to a strict JSON schema to ensure Aki's "Vibe" labels (e.g., "Manic Creation") and target parameters (Energy/Valence) can be used for fallback searches if the primary pick is unavailable.

---

## 5. Potential Improvements
*   **Genre Vectors:** Ingesting the user's top genres to further refine the "Aki Psychologist" persona.
*   **Playback Integration:** Triggering the Spotify Web Playback SDK to play the song immediately upon opening the app.
