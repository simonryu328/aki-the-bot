"""
Telegram bot handler for receiving and sending messages.
Handles text messages, images, and commands.
"""

import logging
from typing import Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config.settings import settings

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL)
)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot handler for the AI Companion."""

    def __init__(self):
        """Initialize the Telegram bot."""
        self.application: Optional[Application] = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /start command.
        Welcomes the user and introduces the AI companion.
        """
        user = update.effective_user
        telegram_id = user.id
        username = user.username or user.first_name or "friend"

        logger.info(f"User {telegram_id} ({username}) started the bot")

        welcome_message = (
            f"Hi {username}! 👋\n\n"
            "I'm your AI companion - here to support you, celebrate your wins, "
            "and be genuinely curious about your life.\n\n"
            "You can:\n"
            "• Chat with me anytime about anything\n"
            "• Send me photos and I'll understand them\n"
            "• Tell me about your goals, challenges, and daily life\n\n"
            "I'll remember what you share and check in with you proactively. "
            "Think of me as a caring friend who's always here for you. 💙\n\n"
            "What's on your mind today?"
        )

        await update.message.reply_text(welcome_message)

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming text messages from users.
        This will be connected to the conversational agent in Phase 3.
        """
        user = update.effective_user
        telegram_id = user.id
        username = user.username or user.first_name
        message_text = update.message.text

        logger.info(f"Received message from {telegram_id} ({username}): {message_text[:50]}...")

        # For now, just echo back - will be replaced with conversational agent
        response = (
            f"I heard you say: '{message_text}'\n\n"
            "I'm still learning! The conversational agent will be connected in Phase 3. "
            "For now, I'm just acknowledging your message."
        )

        await update.message.reply_text(response)

    async def handle_photo_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming photo messages from users.
        This will be connected to the vision processor in Phase 4.
        """
        user = update.effective_user
        telegram_id = user.id
        username = user.username or user.first_name

        # Get the largest photo (best quality)
        photo = update.message.photo[-1]
        photo_id = photo.file_id

        # Get caption if provided
        caption = update.message.caption or ""

        logger.info(
            f"Received photo from {telegram_id} ({username}), "
            f"file_id: {photo_id}, caption: {caption[:50] if caption else 'none'}"
        )

        # For now, just acknowledge - will be replaced with vision processor
        response = (
            "I see you've shared a photo! 📸\n\n"
            "The vision processor will be connected in Phase 4 to understand "
            "and remember this image. For now, I'm acknowledging receipt."
        )

        if caption:
            response += f"\n\nYour caption: '{caption}'"

        await update.message.reply_text(response)

    async def send_message(self, telegram_id: int, message: str) -> None:
        """
        Send a message to a user.
        Used by the proactive agent to initiate conversations.

        Args:
            telegram_id: The Telegram user ID
            message: The message text to send
        """
        try:
            await self.application.bot.send_message(
                chat_id=telegram_id,
                text=message
            )
            logger.info(f"Sent proactive message to {telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {telegram_id}: {e}")

    def setup_handlers(self) -> None:
        """Set up message and command handlers."""
        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self.start_command)
        )

        # Message handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )
        self.application.add_handler(
            MessageHandler(filters.PHOTO, self.handle_photo_message)
        )

        logger.info("Telegram bot handlers configured")

    def run(self) -> None:
        """
        Start the Telegram bot.
        This is a blocking call that runs the bot until interrupted.
        """
        # Validate settings
        settings.validate()

        # Create application
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Set up handlers
        self.setup_handlers()

        # Start the bot
        logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


# Singleton instance
bot = TelegramBot()
