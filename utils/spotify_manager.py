
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config.settings import settings

logger = logging.getLogger(__name__)

class SpotifyManager:
    def __init__(self):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.redirect_uri = settings.SPOTIFY_REDIRECT_URI
        
        # Scopes Aki needs:
        # user-read-recently-played: To see what you've been listening to
        # user-top-read: To understand your general taste
        # user-read-playback-state: To see what's playing now
        # playlist-read-private: To see your playlists
        self.scope = "user-read-recently-played user-top-read user-read-playback-state"

    def get_auth_manager(self) -> Optional[SpotifyOAuth]:
        """Returns the auth manager if credentials are set."""
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            logger.warning("Spotify credentials not fully configured in settings.")
            return None
            
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            open_browser=False
        )

    def get_auth_url(self, state: str) -> Optional[str]:
        """Generates the Spotify authorization URL."""
        auth_manager = self.get_auth_manager()
        if not auth_manager:
            return None
        return auth_manager.get_authorize_url(state=state)

    async def get_token_from_code(self, code: str) -> Dict[str, Any]:
        """Exchanges an auth code for access/refresh tokens."""
        auth_manager = self.get_auth_manager()
        if not auth_manager:
            return {}
        return auth_manager.get_access_token(code, as_dict=True)

    def get_client(self, access_token: str) -> spotipy.Spotify:
        """Returns an authenticated spotipy client."""
        return spotipy.Spotify(auth=access_token)

    async def get_recommendations(self, access_token: str, genres: List[str] = None, artist_ids: List[str] = None, track_ids: List[str] = None, limit: int = 1, **kwargs) -> List[Dict[str, Any]]:
        """Fetches track recommendations based on seeds."""
        sp = self.get_client(access_token)
        try:
            results = sp.recommendations(seed_genres=genres, seed_artists=artist_ids, seed_tracks=track_ids, limit=limit, **kwargs)
            return results.get('tracks', [])
        except Exception as e:
            logger.error(f"Error fetching Spotify recommendations: {e}")
            return []

    async def get_top_tracks(self, access_token: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches user's top tracks."""
        sp = self.get_client(access_token)
        try:
            results = sp.current_user_top_tracks(limit=limit, time_range='short_term')
            return results.get('items', [])
        except Exception as e:
            logger.error(f"Error fetching Spotify top tracks: {e}")
            return []

    async def get_recently_played(self, access_token: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches user's recently played tracks."""
        sp = self.get_client(access_token)
        try:
            results = sp.current_user_recently_played(limit=limit)
            return results.get('items', [])
        except Exception as e:
            logger.error(f"Error fetching Spotify recent history: {e}")
            return []

    async def get_audio_features(self, access_token: str, track_ids: List[str]) -> Dict[str, Any]:
        """
        Fetches audio features for a list of track IDs in batches.
        Spotify API allows up to 100 IDs per request.
        """
        sp = self.get_client(access_token)
        features_map = {}
        
        # Deduplicate IDs and filter out empty ones
        unique_ids = list(set([tid for tid in track_ids if tid]))
        
        # Process in chunks of 100
        chunk_size = 100
        for i in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[i:i + chunk_size]
            try:
                results = sp.audio_features(tracks=chunk)
                for feature in results:
                    if feature:
                        features_map[feature['id']] = feature
            except Exception as e:
                logger.error(f"Error fetching audio features for chunk: {e}")
                
        return features_map

    async def get_artists(self, access_token: str, artist_ids: List[str]) -> Dict[str, Any]:
        """
        Fetches artist details (including genres) for a list of artist IDs.
        Spotify API allows up to 50 IDs per request.
        """
        sp = self.get_client(access_token)
        artists_map = {}
        
        # Deduplicate IDs
        unique_ids = list(set([aid for aid in artist_ids if aid]))
        
        # Process in chunks of 50
        chunk_size = 50
        for i in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[i:i + chunk_size]
            try:
                results = sp.artists(artists=chunk)
                for artist in results.get('artists', []):
                    if artist:
                        artists_map[artist['id']] = artist
            except Exception as e:
                logger.error(f"Error fetching artist details for chunk: {e}")
                
        return artists_map

    async def refresh_user_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refreshes the access token using the refresh token."""
        auth_manager = self.get_auth_manager()
        if not auth_manager:
            return None
        try:
            token_info = auth_manager.refresh_access_token(refresh_token)
            return token_info
        except Exception as e:
            logger.error(f"Error refreshing Spotify token: {e}")
            return None

    async def get_valid_token(self, user: Any) -> Optional[str]:
        """Gets a valid access token for the user, refreshing if necessary."""
        if not user.spotify_refresh_token:
            return None
            
        # Check if expired (with 1 min buffer)
        now = datetime.utcnow()
        if user.spotify_token_expires_at and user.spotify_token_expires_at > (now + timedelta(minutes=1)):
            return user.spotify_access_token
            
        # Refresh needed
        logger.info(f"Refreshing Spotify token for user {user.id}")
        token_info = await self.refresh_user_token(user.spotify_refresh_token)
        if token_info:
            from memory.database_async import db
            new_expires_at = datetime.utcnow() + timedelta(seconds=token_info['expires_in'])
            await db.update_user_spotify_tokens(
                user_id=user.id,
                access_token=token_info['access_token'],
                refresh_token=token_info.get('refresh_token', user.spotify_refresh_token),
                expires_at=new_expires_at
            )
            return token_info['access_token']
            
        return None

spotify_manager = SpotifyManager()
