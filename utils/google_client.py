import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import requests

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config.settings import settings
from memory.database_async import db

logger = logging.getLogger(__name__)

# Scopes Aki needs for companion-native features
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
]

class GoogleClient:
    """Manages Google OAuth flow and token lifecycle."""

    def __init__(self):
        # Use settings instead of raw os.environ
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI.strip() if settings.GOOGLE_REDIRECT_URI else "http://localhost:8000/api/google/callback"
        
        # In-memory client config for Google auth flow
        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "project_id": settings.GOOGLE_PROJECT_ID,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": self.client_secret,
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_auth_url(self, telegram_id: int) -> str:
        """Get the URL to redirect the user to for Google login."""
        # Build the auth URL manually to avoid PKCE code_verifier being
        # injected by the Flow object (which we can't persist server-side).
        from urllib.parse import urlencode
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "state": str(telegram_id),
            "prompt": "consent",
        }
        return "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)

    async def handle_callback(self, code: str, telegram_id: int) -> Dict[str, Any]:
        """Exchange auth code for tokens and store in DB."""
        # Exchange the authorization code for tokens directly via HTTP.
        # This avoids the PKCE 'missing code verifier' issue that happens
        # when using the stateful Flow object across separate requests.
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        scopes = token_data.get("scope", " ".join(SCOPES))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Store tokens in DB
        await db.update_user_google_tokens(
            user_id=telegram_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=scopes,
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
        }

    async def get_valid_token(self, user) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        if not user or not user.google_refresh_token:
            return None

        credentials = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=user.google_scopes.split(" ") if user.google_scopes else SCOPES
        )

        if credentials.expired:
            try:
                credentials.refresh(Request())
                # Update tokens in DB
                await db.update_user_google_tokens(
                    user_id=user.id,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token, # Google might rotate refresh tokens
                    expires_at=credentials.expiry
                )
            except Exception as e:
                logger.error(f"Failed to refresh Google token for user {user.id}: {e}")
                return None

        return credentials.token

    async def build_service(self, user, api_name: str, version: str):
        """Build a Google API service object."""
        token = await self.get_valid_token(user)
        if not token:
            return None
        
        credentials = Credentials(token=token)
        return build(api_name, version, credentials=credentials)

google_client = GoogleClient()
