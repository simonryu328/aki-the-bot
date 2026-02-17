
import asyncio
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from memory.database_async import db
from utils.spotify_manager import spotify_manager
from prompts.spotify_dj import SPOTIFY_DJ_PROMPT
from collections import Counter

async def simulate_for_simon():
    user_id = 1
    print(f"--- Simulating Spotify DJ for User {user_id} (Simon) ---")
    
    # 1. Get user
    user = await db.get_user_by_id(user_id)
    if not user:
        print("User 1 not found in DB.")
        return

    if not user.spotify_refresh_token:
        print("User 1 has no Spotify connection.")
        return

    # 2. Get Token
    access_token = await spotify_manager.get_valid_token(user)
    if not access_token:
        print("Failed to get valid Spotify token.")
        return

    # 3. Fetch Data (Mirroring SoulAgent Logic)
    print("Fetching Top Tracks (50)...")
    top_tracks = await spotify_manager.get_top_tracks(access_token, limit=50)
    print("Fetching Recently Played (50)...")
    recent_tracks = await spotify_manager.get_recently_played(access_token, limit=50)
    
    all_track_ids = [t['id'] for t in top_tracks] + [t['track']['id'] for t in recent_tracks]
    all_artist_ids = [t['artists'][0]['id'] for t in top_tracks]
    
    print("Fetching Audio Features...")
    audio_features_map = await spotify_manager.get_audio_features(access_token, all_track_ids)
    print("Fetching Artist Details...")
    artists_map = await spotify_manager.get_artists(access_token, all_artist_ids)
    
    # 4. Aggregate Stats
    valences = []
    energies = []
    bpms = []
    all_genres = []
    
    for tid in all_track_ids:
        feat = audio_features_map.get(tid)
        if feat:
            valences.append(feat.get('valence', 0.5))
            energies.append(feat.get('energy', 0.5))
            if feat.get('tempo'): bpms.append(feat['tempo'])
    
    for aid in all_artist_ids:
        artist = artists_map.get(aid)
        if artist and artist.get('genres'):
            all_genres.extend(artist['genres'])
    
    avg_valence = sum(valences) / len(valences) if valences else 0.5
    avg_energy = sum(energies) / len(energies) if energies else 0.5
    avg_bpm = int(sum(bpms) / len(bpms)) if bpms else 100
    top_genres = [g[0] for g in Counter(all_genres).most_common(5)]
    
    sonic_profile = (
        f"**Sonic DNA (Average):**\n"
        f"- Valence (Positiveness): {avg_valence:.2f}/1.0\n"
        f"- Energy (Intensity): {avg_energy:.2f}/1.0\n"
        f"- Tempo: ~{avg_bpm} BPM\n"
        f"- Top Genres: {', '.join(top_genres)}"
    )
    
    top_tracks_text = "\n".join([f"- {t['name']} by {t['artists'][0]['name']}" for t in top_tracks[:10]])
    recent_tracks_text = "\n".join([f"- {t['track']['name']} by {t['track']['artists'][0]['name']}" for t in recent_tracks[:10]])

    # 5. Get Conversational Context (Mocking the SoulAgent helper)
    full_history = await db.get_recent_conversations(user_id, limit=30)
    # Simplified context version for simulation
    history_text = "\n".join([f"{'User' if msg.role == 'user' else 'Aki'}: {msg.message}" for msg in full_history[:10]])
    context_text = "Simulated context from recent memories."

    # 6. Construct Final Prompt
    final_prompt = SPOTIFY_DJ_PROMPT.format(
        user_name=user.name or "Simon",
        context=context_text,
        recent_history=history_text,
        sonic_profile=sonic_profile,
        top_tracks=top_tracks_text,
        recently_played=recent_tracks_text
    )

    # 7. Ask LLM to choose the song
    print("Calling LLM for recommendation...")
    from config.settings import settings
    from utils.llm_client import llm_client
    import re

    response = await llm_client.chat(
        model=settings.MODEL_INSIGHTS,
        messages=[{"role": "user", "content": final_prompt}],
        temperature=0.8,
        max_tokens=600,
    )
    
    content = response.content if hasattr(response, 'content') else str(response)
    
    # Parse JSON
    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
    dj_data = json.loads(json_match.group(1)) if json_match else {}

    # 7. Write to Output File
    report_content = f"""# Spotify DJ Simulation Report: Simon (User 1)
Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. Aggregated Data (Aki's Observations)
{sonic_profile}

## 2. THE CHOSEN SONG
**Vibe:** {dj_data.get('vibe_description')}
**Song:** {dj_data.get('search_query')}
**Explanation:** {dj_data.get('explanation')}

### Thought Process:
{dj_data.get('thought')}

## 3. THE FULL PROMPT (SENT TO LLM)
```text
{final_prompt}
```
"""
    
    output_path = "docs/simulation_report_simon.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"Simulation complete! Report written to {output_path}")

if __name__ == "__main__":
    asyncio.run(simulate_for_simon())
