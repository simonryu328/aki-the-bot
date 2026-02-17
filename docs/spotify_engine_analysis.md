# Spotify Engine Analysis & Improvement Plan

## 1. Current State Analysis

### The Input Data (What we fetch)
Currently, `SoulAgent` calls `spotify_manager.get_top_tracks(limit=5)`.
Spotify returns a list of **Track Objects**. Each object contains ~30 fields.

**The Fields We Receive (The "30 Fields"):**
1.  `album`: { `name`, `release_date`, `images`: [...] }
2.  `artists`: [{ `name`, `id`, `uri` }, ...]
3.  `available_markets`: ["US", "CA", ...]
4.  `disc_number`: int
5.  `duration_ms`: int (e.g., 245000)
6.  `explicit`: boolean (True/False)
7.  `external_ids`: { `isrc`: "..." }
8.  `external_urls`: { `spotify`: "..." }
9.  `href`: string (API link)
10. `id`: string (Spotify ID)
11. `is_local`: boolean
12. `is_playable`: boolean
13. `name`: string ("Song Title")
14. `popularity`: int (0-100)
15. `preview_url`: string (MP3 link, often null)
16. `track_number`: int
17. `type`: "track"
18. `uri`: string ("spotify:track:...")
*(Plus ~10 internal/linking fields)*

### The Bottleneck (What we actually use)
Despite receiving all of the above, **`SoulAgent` performs a "Lossy Compression"** before talking to the LLM.

**Current Logic:**
```python
top_tracks_text = "\n".join([f"- {t['name']} by {t['artists'][0]['name']}" for t in top_tracks])
```

**The Reality:**
Aki **discards 98% of the data**.
-   **No Metadata Used:** Matches are made purely on **text association**.
-   **Inference Method:** The LLM sees "Song X by Artist Y" and uses its *pre-trained training data* to guess the vibe.
    -   *Example:* It sees "Mr. Brightside by The Killers".
    -   *LLM Thinks:* "My internal database says this is 2000s Indie Rock, high energy."
    -   *Reality:* It does **not** know if you were listening to a slow acoustic cover version or the original, because it didn't look at the ID or audio features.

---

## 2. Improvement Plan: The "Deep Listening" Upgrade

To make Aki truly intelligent, we need to move from **Text Association** to **Audio Feature Analysis**.

### Step 1: Fetch The Missing "Audio Features"
We need to add a secondary API call: `sp.audio_features(track_ids)`.
This returns the **Quantitative DNA** of the music.

| Feature | Description | Why we need it |
| :--- | :--- | :--- |
| **Valence** (0-1) | Musical Positiveness | Tells us if you are happy (0.9) or depressed (0.2). |
| **Energy** (0-1) | Intensity/Activity | Tells us if you are manic (0.9) or chill (0.3). |
| **Danceability** (0-1) | Rhythm Stability | Are you working out/partying or studying? |
| **Tempo** (BPM) | Speed | Fast = Anxiety/Excitement; Slow = Relaxing/Sad. |
| **Mode** (0/1) | Major/Minor Key | Major = Bright; Minor = Emotional/Dark. |

### Step 2: Create a "Taste Profile"
Instead of listing 5 song titles, we calculate the **average** of these stats to create a "Current Vibe Profile" for the LLM.

**New Prompt Input:**
> **User's Current Sonic Profile (Last 4 Weeks):**
> *   **Mood:** Melancholic (Valence: 0.25)
> *   **Energy:** Very Low (Energy: 0.3)
> *   **Tempo:** Slow (Avg 85 BPM)
> *   **Top Genres:** Indie Folk, Ambient
> *   **Representative Tracks:**
>     *   *Exile* (Taylor Swift) - Sad, Slow
>     *   *Holocene* (Bon Iver) - Sad, Atmospheric

### Step 3: Objective Reasoning
With this data, the LLM stops guessing and starts **reasoning**:
*   *Old Logic:* "User likes Bon Iver, so maybe they are sad?"
*   *New Logic:* "User's average Valence is 0.2 (Severe Sadness) and Energy is 0.3 (Low). They are in a depressive slump. I should recommend something to match this (empathy) or gently lift them (intervention)."

### Step 4: Better Fallbacks
If Aki creates a search query that fails, we can use the **User's Actual Averages** as the `target_energy` and `target_valence` for the fallback recommendation engine, ensuring the backup song *actually* sounds like something they would play.

## Implementation Checklist
1.  [ ] Update `SpotifyManager` to fetch `audio_features` for the top 5 track IDs.
2.  [ ] Create a helper to calculate the "Average Taste Profile" (Avg Valence, Energy, BPM).
3.  [ ] Update `SPOTIFY_DJ_PROMPT` to accept these quantitative stats.
4.  [ ] Update `SoulAgent` to pass this enriched data to the LLM.
