"""
Audio Manager for Text-to-Speech (TTS) using OpenAI.
"""

import os
from io import BytesIO
from typing import Optional
from openai import AsyncOpenAI

from config.settings import settings
from core import get_logger

logger = get_logger(__name__)

class AudioManager:
    """Manages audio generation and processing."""

    def __init__(self):
        """Initialize OpenAI client for TTS."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("Audio manager initialized with OpenAI TTS")

    async def generate_tts(
        self, 
        text: str, 
        model: str = settings.TTS_MODEL, 
        voice: str = settings.TTS_VOICE
    ) -> Optional[BytesIO]:
        """
        Generate audio from text using OpenAI TTS.
        
        Args:
            text: The text to convert to speech
            model: TTS model to use
            voice: The voice to use
            
        Returns:
            BytesIO object containing the audio data (MP3/OPUS) or None if failed
        """
        try:
            logger.info(f"Generating TTS for text ({len(text)} chars) using {voice}")
            
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format="opus"  # Telegram voice notes prefer OGG/OPUS
            )
            
            # Convert response to BytesIO
            audio_data = BytesIO()
            # The response content can be streamed or read all at once
            audio_data.write(await response.aread())
            audio_data.seek(0)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

# Singleton instance
audio_manager = AudioManager()
