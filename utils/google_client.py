import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from google.api_core import exceptions
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
        self.client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/google/callback")
        
        # In-memory client config for Google auth flow
        self.client_config = {
            "web": {
                "client_id": self.client_id,
                "project_id": os.environ.get("GOOGLE_PROJECT_ID"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": self.client_secret,
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_auth_url(self, telegram_id: int) -> str:
        """Get the URL to redirect the user to for Google login."""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        # State parameter carries the telegram_id to link the session back
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=str(telegram_id),
            prompt='consent'
        )
        return auth_url

    async def handle_callback(self, code: str, telegram_id: int) -> Dict[str, Any]:
        """Exchange auth code for tokens and store in DB."""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Store tokens in DB
        await db.update_user_google_tokens(
            user_id=telegram_id, # Using telegram_id as user_id for simplicity if needed, but db method should match user internal ID
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_at=credentials.expiry,
            scopes=" ".join(credentials.scopes)
        )
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expires_at": credentials.expiry.isoformat()
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
